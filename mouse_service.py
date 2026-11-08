import platform
import ctypes
import time
from pynput.mouse import Controller, Button

# macOS 兼容性补丁：处理某些 pyobjc 版本缺失 CGDisplayPixelsHigh 的问题
if platform.system() == 'Darwin':
    try:
        import Quartz
        if not hasattr(Quartz, 'CGDisplayPixelsHigh'):
            def CGDisplayPixelsHigh(display_id):
                return int(Quartz.CGDisplayBounds(display_id).size.height)
            Quartz.CGDisplayPixelsHigh = CGDisplayPixelsHigh
    except Exception:
        pass

mouse = Controller()
_is_dragging = False

# 屏幕可视范围边界缓存 (min_x, min_y, max_x, max_y)
_screen_bounds = None
_last_bounds_update = 0.0

# Windows 唤醒光标防抖节流时间戳
_last_wake_time = 0.0

def update_screen_bounds():
    """获取所有显示器的全局联合可视边界，避免逻辑光标被推到屏幕外部"""
    global _screen_bounds, _last_bounds_update
    now = time.time()
    if _screen_bounds is not None and (now - _last_bounds_update) < 3.0:
        return _screen_bounds

    bounds = None
    sys_name = platform.system()

    if sys_name == 'Darwin':
        try:
            import Quartz
            err, displays, count = Quartz.CGGetActiveDisplayList(16, None, None)
            if not err and count > 0:
                min_x = float('inf')
                min_y = float('inf')
                max_x = float('-inf')
                max_y = float('-inf')
                for d in displays[:count]:
                    b = Quartz.CGDisplayBounds(d)
                    min_x = min(min_x, b.origin.x)
                    min_y = min(min_y, b.origin.y)
                    max_x = max(max_x, b.origin.x + b.size.width)
                    max_y = max(max_y, b.origin.y + b.size.height)
                # 边缘最大坐标为 width - 1，确保光标永远位于物理像素矩阵内
                bounds = (min_x, min_y, max_x - 1, max_y - 1)
        except Exception:
            pass

    elif sys_name == 'Windows':
        try:
            SM_XVIRTUALSCREEN = 76
            SM_YVIRTUALSCREEN = 77
            SM_CXVIRTUALSCREEN = 78
            SM_CYVIRTUALSCREEN = 79
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
            vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
            if vw > 0 and vh > 0:
                bounds = (float(vx), float(vy), float(vx + vw - 1), float(vy + vh - 1))
            else:
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
                bounds = (0.0, 0.0, float(sw - 1), float(sh - 1))
        except Exception:
            pass

    if not bounds:
        bounds = (0.0, 0.0, 1919.0, 1079.0)

    _screen_bounds = bounds
    _last_bounds_update = now
    return bounds

def wake_up_cursor():
    """唤醒触控设备上的隐藏光标（防抖节流，绝不使用 sleep 阻塞事件循环）"""
    global _last_wake_time
    now = time.time()
    if (now - _last_wake_time) < 2.0:
        return
    _last_wake_time = now

    if platform.system() == 'Windows':
        try:
            MOUSEEVENTF_MOVE = 0x0001
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)
        except Exception:
            pass

def handle_move(data):
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    if dx == 0 and dy == 0:
        return

    try:
        cur_pos = mouse.position
        if cur_pos is None:
            mouse.move(dx, dy)
            wake_up_cursor()
            return

        cur_x, cur_y = cur_pos
        min_x, min_y, max_x, max_y = update_screen_bounds()

        # 核心防溢出裁剪：若光标因任何外部原因已脱离屏幕，先拉回边界
        clamped_cur_x = max(min_x, min(max_x, cur_x))
        clamped_cur_y = max(min_y, min(max_y, cur_y))

        # 目标坐标严格限制在屏幕可视矩阵内，绝不向屏幕外溢出
        target_x = max(min_x, min(max_x, clamped_cur_x + dx))
        target_y = max(min_y, min(max_y, clamped_cur_y + dy))

        mouse.position = (target_x, target_y)
    except Exception:
        mouse.move(dx, dy)

    wake_up_cursor()

def reset_mac_modifier_keys():
    """彻底重置 macOS 上所有可能的残留修饰键 (Command, Control, Option, Shift)，防止键位粘滞"""
    if platform.system() != 'Darwin':
        return
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        MODIFIER_KEYCODES = [55, 54, 59, 62, 58, 61, 56, 60]  # Cmd, Ctrl, Alt/Opt, Shift
        for code in MODIFIER_KEYCODES:
            ku = Quartz.CGEventCreateKeyboardEvent(src, code, False)
            Quartz.CGEventSetFlags(ku, 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ku)
    except Exception:
        pass

def safe_mac_mouse_event(event_type, mouse_button, click_count=1):
    """在 macOS 上以绝对纯净的 0 标志位发送鼠标事件，彻底杜绝继承任何残留的 Command/Shift 键"""
    try:
        import Quartz
        pos = mouse.position
        cg_point = Quartz.CGPoint(pos[0], pos[1])
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        ev = Quartz.CGEventCreateMouseEvent(src, event_type, cg_point, mouse_button)
        # 核心安全保障：强制将事件修饰标志置为 0，防止 Dock 图标被当成 Cmd+Click 打开目录
        Quartz.CGEventSetFlags(ev, 0)
        if click_count > 0:
            Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, click_count)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        return True
    except Exception:
        return False

def handle_click(data):
    button_type = data.get('button')
    if platform.system() == 'Darwin':
        import Quartz
        btn_map = {
            'left': (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft),
            'right': (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight),
            'middle': (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGMouseButtonCenter)
        }
        if button_type in btn_map:
            # 点击前确保修饰键纯净，绝不残留 Command 键
            reset_mac_modifier_keys()
            down_type, up_type, btn = btn_map[button_type]
            safe_mac_mouse_event(down_type, btn, 1)
            time.sleep(0.01)
            safe_mac_mouse_event(up_type, btn, 1)
            return

    if button_type == 'left':
        mouse.click(Button.left)
    elif button_type == 'right':
        mouse.click(Button.right)
    elif button_type == 'middle':
        mouse.click(Button.middle)
    elif button_type == 'x1':
        mouse.click(Button.x1)
    elif button_type == 'x2':
        mouse.click(Button.x2)

def handle_drag_start():
    global _is_dragging
    if not _is_dragging:
        if platform.system() == 'Darwin':
            import Quartz
            reset_mac_modifier_keys()
            safe_mac_mouse_event(Quartz.kCGEventLeftMouseDown, Quartz.kCGMouseButtonLeft, 1)
        else:
            mouse.press(Button.left)
        _is_dragging = True

def handle_drag_end():
    global _is_dragging
    if platform.system() == 'Darwin':
        import Quartz
        safe_mac_mouse_event(Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft, 1)
        reset_mac_modifier_keys()
    else:
        mouse.release(Button.left)
    _is_dragging = False

def handle_mid_down():
    mouse.release(Button.middle)
    mouse.press(Button.middle)

def handle_mid_up():
    mouse.release(Button.middle)

def handle_scroll(data):
    # dx: 水平, dy: 垂直
    dx = data.get('dx', 0)
    dy = data.get('dy', 0)
    
    # macOS 滚动方向通常与 Windows 相反
    if platform.system() == 'Darwin':
        mouse.scroll(-dx, -dy)
    else:
        mouse.scroll(dx, dy)
