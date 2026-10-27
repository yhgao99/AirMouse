/**
 * Touchpad Module for AirMouse (Enhanced Apple-like Trackpad Experience)
 * Includes:
 * 1. Multi-tier Haptic & Audio Tactile Feedback (Taptic Engine emulation)
 * 2. 2D Free Momentum / Inertia Scrolling with touch-to-stop physics
 * 3. Dynamic non-linear cursor acceleration (precision micro-movements + flick across screens)
 * 4. Multi-touch gesture recognition (left click, right click, middle click, drag lock)
 * 5. Screen Wake Lock
 */

class HapticFeedback {
    constructor() {
        this.audioCtx = null;
    }

    init() {
        if (!this.audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) this.audioCtx = new AudioContext();
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    }

    // 类型：click(单指), right_click(双指右键), drag_lock(长按锁定), drag_release(松开释放)
    trigger(type = 'click') {
        this.init();
        if (type === 'click') {
            // 单指轻点：清脆微动 (10ms)
            if (navigator.vibrate) navigator.vibrate(10);
            this._clickSound(820, 0.04, 0.03);
        } else if (type === 'right_click') {
            // 双指右键：两段触感脉冲
            if (navigator.vibrate) navigator.vibrate([10, 35, 12]);
            this._clickSound(950, 0.04, 0.03);
            setTimeout(() => this._clickSound(750, 0.04, 0.03), 40);
        } else if (type === 'drag_lock') {
            // 锁定拖拽：深沉重击 (Force Click 感觉)
            if (navigator.vibrate) navigator.vibrate(28);
            this._clickSound(450, 0.08, 0.06);
        } else if (type === 'drag_release') {
            // 释放拖拽：轻巧回弹
            if (navigator.vibrate) navigator.vibrate(8);
            this._clickSound(650, 0.03, 0.03);
        }
    }

    _clickSound(freq, volume, duration) {
        if (!this.audioCtx) return;
        try {
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);
            gain.gain.setValueAtTime(volume, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.start();
            osc.stop(this.audioCtx.currentTime + duration);
        } catch (e) {}
    }
}

class Touchpad {
    constructor(elementId, socket, options = {}) {
        this.pad = document.getElementById(elementId);
        if (!this.pad) return;

        this.socket = socket;
        this.getSensitivity = options.getSensitivity || (() => 4.0);
        this.haptics = new HapticFeedback();

        this.lx = 0; this.ly = 0; // last x, y
        this.sx = 0; this.sy = 0; // start x, y
        this.hMove = false;
        this.tCount = 0;
        this.maxTCount = 0;
        this.drag = false;
        this.isThreeFingerDrag = false;
        this.longPressTimer = null;
        this.lastMultiTouchTime = 0;

        // 四指系统手势状态
        this.fourFingerStart = null;
        this.fourFingerTriggered = false;
        this._toastTimer = null;
        if (this.pad && getComputedStyle(this.pad).position === 'static') {
            this.pad.style.position = 'relative';
        }

        // 惯性滚动与速度追踪
        this.scrollAccumX = 0;
        this.scrollAccumY = 0;
        this.scrollHistory = [];
        this.inertiaAnimId = null;

        this._bindEvents();
    }

    _bindEvents() {
        this.pad.oncontextmenu = (e) => e.preventDefault();
        this.pad.addEventListener('contextmenu', e => e.preventDefault());

        this.pad.addEventListener('touchstart', e => {
            if (e.cancelable) e.preventDefault();
            this._handleTouchStart(e);
        }, { passive: false });

        this.pad.addEventListener('touchmove', e => {
            if (e.cancelable) e.preventDefault();
            this._handleTouchMove(e);
        }, { passive: false });

        this.pad.addEventListener('touchend', e => this._handleTouchEnd(e));
        this.pad.addEventListener('touchcancel', () => this._handleTouchCancel());
    }

    _stopInertia() {
        if (this.inertiaAnimId) {
            cancelAnimationFrame(this.inertiaAnimId);
            this.inertiaAnimId = null;
        }
    }

    _startInertia(vx, vy) {
        this._stopInertia();
        // 将 px/ms 转换为每帧步长增量
        let curVx = vx * 5.5;
        let curVy = vy * 5.5;
        const DECAY = 0.91; // 经典阻尼衰减系数
        let subX = 0;
        let subY = 0;

        const step = () => {
            curVx *= DECAY;
            curVy *= DECAY;
            subX += curVx;
            subY += curVy;

            let sx = Math.trunc(subX);
            let sy = Math.trunc(subY);
            subX -= sx;
            subY -= sy;

            if (sx !== 0 || sy !== 0) {
                this.socket.emit('scroll', { dx: sx, dy: sy });
            }

            if (Math.hypot(curVx, curVy) > 0.12) {
                this.inertiaAnimId = requestAnimationFrame(step);
            } else {
                this.inertiaAnimId = null;
            }
        };

        this.inertiaAnimId = requestAnimationFrame(step);
    }

    _showGestureToast(msg) {
        if (!this.pad) return;
        let toast = this.pad.querySelector('.touchpad-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'touchpad-toast';
            toast.style.cssText = `
                position: absolute;
                top: 18px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(15, 23, 42, 0.92);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                color: #38bdf8;
                padding: 7px 18px;
                border-radius: 20px;
                font-size: 13.5px;
                font-weight: 600;
                letter-spacing: 0.3px;
                pointer-events: none;
                z-index: 999;
                box-shadow: 0 4px 18px rgba(0,0,0,0.45);
                border: 1px solid rgba(56, 189, 248, 0.35);
                transition: opacity 0.22s ease, transform 0.22s ease;
                opacity: 0;
                white-space: nowrap;
            `;
            this.pad.appendChild(toast);
        }
        toast.textContent = msg;
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(-50%) translateY(0)';
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(-6px)';
        }, 900);
    }

    _getCentroid(e) {
        const touches = e.targetTouches;
        const n = touches.length;
        if (n === 0) return { x: this.lx, y: this.ly };
        let sx = 0, sy = 0;
        for (let i = 0; i < n; i++) {
            sx += touches[i].clientX;
            sy += touches[i].clientY;
        }
        return { x: sx / n, y: sy / n };
    }

    _handleTouchStart(e) {
        // 苹果触控板核心体验：只要手指重新接触屏幕，立刻截停任何正在进行的惯性滑行 (Catch-to-stop)
        this._stopInertia();
        this.scrollAccumX = 0;
        this.scrollAccumY = 0;
        this.scrollHistory = [];

        this.haptics.init();

        const prevTCount = this.tCount;
        this.tCount = e.targetTouches.length;

        if (this.tCount === 1 && prevTCount === 0) {
            this.maxTCount = 1;
        } else {
            this.maxTCount = Math.max(this.maxTCount, this.tCount);
        }

        const center = this._getCentroid(e);
        this.lx = center.x;
        this.ly = center.y;
        this.sx = this.lx;
        this.sy = this.ly;
        this.hMove = false;

        // 单指长按 420ms 进入拖拽锁定模式
        if (this.tCount === 1) {
            this.longPressTimer = setTimeout(() => {
                this.drag = true;
                this.isThreeFingerDrag = false;
                this.socket.emit('drag_start');
                this.pad.style.background = "#001a33";
                this.haptics.trigger('drag_lock');
            }, 420);
        }

        // 三指视觉反馈 (三指触控即进入就绪拖拽背景)
        if (this.tCount === 3) {
            this.pad.style.background = "#001a33";
        }

        // 四指就绪
        if (this.tCount === 4) {
            if (!this.fourFingerTriggered) {
                this.fourFingerStart = { x: center.x, y: center.y, time: Date.now() };
                this.pad.style.background = "#0f172a";
                this.haptics.trigger('click');
            }
        }
    }

    _handleTouchMove(e) {
        e.preventDefault();
        const prevTCount = this.tCount;
        this.tCount = e.targetTouches.length;
        this.maxTCount = Math.max(this.maxTCount, this.tCount);

        const center = this._getCentroid(e);
        const cx = center.x, cy = center.y;

        // 多指到单指切换锁定 (300ms 缓冲防手抖)
        if (prevTCount >= 2 && this.tCount === 1) {
            this.lastMultiTouchTime = Date.now();
        }

        // --- 四指原生系统手势识别 (调度中心 / 桌面切换 / 显示桌面) ---
        // 关键保护：一旦本轮触摸曾达到 4 指 (maxTCount >= 4)，哪怕划动中偶有 1 指轻微离屏，也绝不降级为三指拖拽！
        if (this.maxTCount >= 4) {
            if (!this.fourFingerStart) {
                this.fourFingerStart = { x: cx, y: cy, time: Date.now() };
            }
            if (!this.fourFingerTriggered) {
                const dx = cx - this.fourFingerStart.x;
                const dy = cy - this.fourFingerStart.y;
                const dist = Math.hypot(dx, dy);

                // 划动超过 26px 灵敏响应
                if (dist > 26) {
                    this.fourFingerTriggered = true;
                    if (Math.abs(dy) > Math.abs(dx)) {
                        if (dy < 0) {
                            // 四指向上：调度中心 (Mission Control)
                            this.socket.emit('system_gesture', { action: 'mission_control' });
                            this.haptics.trigger('drag_lock');
                            this._showGestureToast('🚀 调度中心');
                        } else {
                            // 四指向下：App Exposé (应用程序所有窗口, 纯正原生)
                            this.socket.emit('system_gesture', { action: 'app_expose' });
                            this.haptics.trigger('drag_lock');
                            this._showGestureToast('🪟 App Exposé (应用窗口)');
                        }
                    } else {
                        if (dx < 0) {
                            // 四指向左滑：翻向右边下一个桌面 / 全屏应用 (符合苹果翻页物理直觉)
                            this.socket.emit('system_gesture', { action: 'space_right' });
                            this.haptics.trigger('right_click');
                            this._showGestureToast('➡️ 下一个桌面 / 全屏App');
                        } else {
                            // 四指向右滑：翻向左边上一个桌面 / 全屏应用
                            this.socket.emit('system_gesture', { action: 'space_left' });
                            this.haptics.trigger('right_click');
                            this._showGestureToast('⬅️ 上一个桌面 / 全屏App');
                        }
                    }
                }
            }
            this.lx = cx;
            this.ly = cy;
            return;
        }

        // 移动判定阈值
        const moveDist = Math.hypot(cx - this.sx, cy - this.sy);
        // 三指微移 3px 即可判定为拖拽；双指 8px 容差防右键误触；单指 5px
        const moveThreshold = this.tCount === 3 ? 3 : (this.tCount === 2 ? 8 : 5);
        if (moveDist > moveThreshold) {
            this.hMove = true;
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
            // 三指拖拽启动：只要三指开始移动，立刻触发 drag_start
            if (this.tCount === 3 && !this.drag) {
                this.drag = true;
                this.isThreeFingerDrag = true;
                this.socket.emit('drag_start');
                this.haptics.trigger('drag_lock');
                this.pad.style.background = "#001a33";
            }
        }

        const sensitivity = this.getSensitivity();

        // --- 三指拖拽专用光标移动（完全无 300ms 延迟阻滞，丝滑跟随） ---
        if (this.tCount === 3) {
            if (this.drag) {
                const rawDx = cx - this.lx;
                const rawDy = cy - this.ly;
                const dist = Math.hypot(rawDx, rawDy);

                let accel = 1.0;
                if (dist > 5) {
                    accel = 1.0 + Math.min(1.8, (dist - 5) * 0.08);
                }

                this.socket.emit('move', {
                    dx: rawDx * sensitivity * accel,
                    dy: rawDy * sensitivity * accel
                });
            }
            this.lx = cx;
            this.ly = cy;
            return;
        }

        // 若当前处于三指拖拽期间，手指抬起过程中暂时降为 2 指或 1 指，禁止触发双指滚动或光标乱跳
        if (this.isThreeFingerDrag) {
            this.lx = cx;
            this.ly = cy;
            return;
        }

        // --- 单指光标移动（带非线性动态加速度与防误触缓冲） ---
        if (this.tCount === 1) {
            if (Date.now() - this.lastMultiTouchTime > 300) {
                const rawDx = cx - this.lx;
                const rawDy = cy - this.ly;
                const dist = Math.hypot(rawDx, rawDy);

                // 非线性动态加速度曲线
                let accel = 1.0;
                if (dist < 2.5) {
                    accel = 0.75; // 慢速微调降速防抖
                } else if (dist > 8) {
                    accel = 1.0 + Math.min(2.0, (dist - 8) * 0.08); // 快速滑动动态倍增
                }

                this.socket.emit('move', {
                    dx: rawDx * sensitivity * accel,
                    dy: rawDy * sensitivity * accel
                });
            }
            this.lx = cx;
            this.ly = cy;

        // --- 双指 2D 全向物理平滑滚动 ---
        } else if (this.tCount === 2) {
            this.lastMultiTouchTime = Date.now();

            const now = Date.now();
            this.scrollHistory.push({ x: cx, y: cy, time: now });
            if (this.scrollHistory.length > 8) this.scrollHistory.shift();

            const rawDx = cx - this.lx;
            const rawDy = cy - this.ly;

            this.scrollAccumX += rawDx;
            this.scrollAccumY += rawDy;

            // 步进阈值：每 4.5px 触发一次滚动，手感细腻连贯
            const STEP = 4.5;
            let emitDx = 0;
            let emitDy = 0;

            if (Math.abs(this.scrollAccumX) >= STEP) {
                emitDx = Math.trunc(this.scrollAccumX / STEP);
                this.scrollAccumX -= emitDx * STEP;
            }
            if (Math.abs(this.scrollAccumY) >= STEP) {
                emitDy = Math.trunc(this.scrollAccumY / STEP);
                this.scrollAccumY -= emitDy * STEP;
            }

            if (emitDx !== 0 || emitDy !== 0) {
                // 动态速度加权：滑得越快，滚动力度呈倍数放大，再也不慢吞吞！
                const moveSpeed = Math.hypot(rawDx, rawDy);
                const speedMult = moveSpeed > 8 ? Math.min(2.5, 1.0 + (moveSpeed - 8) * 0.1) : 1.0;

                const finalDx = Math.round(emitDx * speedMult);
                const finalDy = Math.round(emitDy * speedMult);

                if (finalDx !== 0 || finalDy !== 0) {
                    this.socket.emit('scroll', { dx: finalDx, dy: finalDy });
                }
            }

            this.lx = cx;
            this.ly = cy;
        }
    }

    _handleTouchEnd(e) {
        const prevTCount = this.tCount;
        this.tCount = e.targetTouches.length;

        if (prevTCount >= 2 && this.tCount === 1) {
            this.lastMultiTouchTime = Date.now();
        }

        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }

        // --- 处理惯性滑行触发 ---
        if (!this.isThreeFingerDrag && prevTCount === 2 && this.tCount === 0 && this.scrollHistory.length >= 2) {
            const pFirst = this.scrollHistory[0];
            const pLast = this.scrollHistory[this.scrollHistory.length - 1];
            const dt = pLast.time - pFirst.time;
            if (dt > 15 && dt < 180) {
                const vx = (pLast.x - pFirst.x) / dt;
                const vy = (pLast.y - pFirst.y) / dt;
                const speed = Math.hypot(vx, vy);
                // 手指甩动初速度足够大时，触发平滑惯性滑冰
                if (speed > 0.35) {
                    this._startInertia(vx, vy);
                }
            }
            this.scrollHistory = [];
        }

        // --- 拖拽与点击手势判定 ---
        if (this.drag) {
            if (this.tCount === 0) {
                this.socket.emit('drag_end');
                this.drag = false;
                this.isThreeFingerDrag = false;
                this.pad.style.background = "";
                this.haptics.trigger('drag_release');
            }
        } else if (this.tCount === 0) {
            if (!this.hMove) {
                if (this.maxTCount === 1) {
                    this.socket.emit('click', { button: 'left' });
                    this.haptics.trigger('click');
                } else if (this.maxTCount === 2) {
                    this.socket.emit('click', { button: 'right' });
                    this.haptics.trigger('right_click');
                } else if (this.maxTCount === 3) {
                    this.socket.emit('click', { button: 'middle' });
                    this.haptics.trigger('click');
                } else if (this.maxTCount >= 4 && !this.fourFingerTriggered) {
                    // 四指轻点 -> 打开启动台 (Launchpad)
                    this.socket.emit('system_gesture', { action: 'launchpad' });
                    this.haptics.trigger('click');
                    this._showGestureToast('📱 启动台 (Launchpad)');
                }
            }
        }

        if (this.tCount === 0) {
            this.maxTCount = 0;
            this.isThreeFingerDrag = false;
            this.fourFingerTriggered = false;
            this.fourFingerStart = null;
            this.pad.style.background = "";
            if (window.stopScroll) window.stopScroll();
        }
    }

    _handleTouchCancel() {
        this.tCount = 0;
        this.maxTCount = 0;
        this.isThreeFingerDrag = false;
        this.fourFingerTriggered = false;
        this.fourFingerStart = null;
        this.pad.style.background = "";
        this._stopInertia();
        if (this.drag) {
            this.socket.emit('drag_end');
            this.drag = false;
            this.haptics.trigger('drag_release');
        }
        if (this.longPressTimer) {
            clearTimeout(this.longPressTimer);
            this.longPressTimer = null;
        }
        if (window.stopScroll) window.stopScroll();
    }

    isLocked() {
        return (Date.now() - this.lastMultiTouchTime < 300);
    }

    getLastMultiTouchTime() {
        return this.lastMultiTouchTime;
    }
}

// Export for use in scripts
window.TouchpadModule = Touchpad;

// --- 自动保持手机屏幕常亮 (Wake Lock) ---
if ('wakeLock' in navigator) {
    let wakeLock = null;
    const requestWakeLock = async () => {
        try {
            if (document.visibilityState === 'visible') {
                wakeLock = await navigator.wakeLock.request('screen');
            }
        } catch (e) {}
    };
    requestWakeLock();
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') requestWakeLock();
    });
}
