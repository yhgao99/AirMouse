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

def handle_click(data):
    button_type = data.get('button')
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
        mouse.press(Button.left)
        _is_dragging = True

def handle_drag_end():
    global _is_dragging
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
