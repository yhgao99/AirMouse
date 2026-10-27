import platform
import os
import sys
import socket
import signal
import subprocess
import tempfile
import threading
import time
import webbrowser

# 优雅处理退出信号
signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

# macOS 激活策略设置：隐藏 Dock 图标，作为后台守护服务静默运行
if platform.system() == 'Darwin':
    try:
        from AppKit import NSBundle, NSApplication, NSApplicationActivationPolicyAccessory
        bundle = NSBundle.mainBundle()
        if bundle:
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info['LSUIElement'] = '1'
        # 设为 Accessory 策略：不在 Dock 栏生成图标，但允许顶部菜单栏与浮窗交互
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass

from web_app import app, socketio, get_all_ip_addresses
from app_paths import app_dir, is_frozen, resource_path
import mouse_service
import keyboard_service
import config_manager
import gamepad_service

PORT = 5888
# Ensure relative config/log paths stay next to the executable.
os.chdir(app_dir())

# 启动手柄后台服务 (如果已安装 inputs)
gamepad_service.start_threads()

def status_thread():
    while True:
        socketio.emit('gp_status', {
            'connected': gamepad_service.gamepad_connected,
            'name': gamepad_service.gamepad_name
        })
        time.sleep(1)

threading.Thread(target=status_thread, daemon=True).start()


def hide_console_window():
    """Hide the attached console window on Windows when launched via python.exe."""
    if platform.system() != 'Windows':
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def open_page(path='/'):
    webbrowser.open(f'https://127.0.0.1:{PORT}{path}', new=2)


def show_info_dialog(title, message, error=False):
    """Show a simple native dialog that works from the tray thread."""
    if platform.system() == 'Windows':
        try:
            import ctypes
            flags = 0x00000010 if error else 0x00000040  # ICONERROR / ICONINFORMATION
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000000 | flags)
            return
        except Exception:
            pass

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        if error:
            messagebox.showerror(title, message, parent=root)
        else:
            messagebox.showinfo(title, message, parent=root)
        root.destroy()
    except Exception:
        pass


def trust_ssl_certificate():
    """Import the bundled self-signed cert into the current user's Trusted Root store."""
    if platform.system() != 'Windows':
        show_info_dialog('信任 SSL 证书', '当前仅支持在 Windows 上自动导入证书。', error=True)
        return

    pem_path = resource_path('cert.pem')
    if not os.path.exists(pem_path):
        show_info_dialog('信任 SSL 证书', '未找到证书文件 cert.pem。', error=True)
        return

    der_path = None
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import Encoding

        with open(pem_path, 'rb') as f:
            cert = x509.load_pem_x509_certificate(f.read())

        fd, der_path = tempfile.mkstemp(suffix='.cer', prefix='airmouse-cert-')
        os.close(fd)
        with open(der_path, 'wb') as f:
            f.write(cert.public_bytes(Encoding.DER))

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(
            ['certutil', '-addstore', '-user', 'Root', der_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=creationflags,
        )

        output = ((result.stdout or '') + '\n' + (result.stderr or '')).strip()
        already = 'already in store' in output.lower() or '已经在存储' in output or '已在存储' in output

        if result.returncode == 0 or already:
            show_info_dialog(
                '信任 SSL 证书',
                '已将 AirMouse 证书导入当前用户的“受信任的根证书颁发机构”。\n\n'
                '请完全退出并重新打开 Chrome / Edge 后再访问本机页面。\n'
                '手机端仍需在手机上自行选择继续访问或信任证书。',
            )
        else:
            show_info_dialog(
                '信任 SSL 证书',
                '导入失败。\n\n' + (output or f'certutil 退出码: {result.returncode}'),
                error=True,
            )
    except Exception as exc:
        show_info_dialog('信任 SSL 证书', f'导入失败：{exc}', error=True)
    finally:
        if der_path and os.path.exists(der_path):
            try:
                os.remove(der_path)
            except OSError:
                pass


def create_tray_image():
    from PIL import Image, ImageDraw

    icon_path = resource_path('static', 'app-icon.png')
    try:
        image = Image.open(icon_path).convert('RGBA')
        return image.resize((64, 64), Image.Resampling.LANCZOS)
    except Exception:
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(16, 38, 26, 255))
        draw.rounded_rectangle((14, 14, 50, 50), radius=8, outline=(89, 227, 145, 255), width=4)
        draw.rectangle((20, 20, 28, 28), fill=(89, 227, 145, 255))
        draw.rectangle((36, 36, 44, 44), fill=(89, 227, 145, 255))
        return image


def start_server():
    socketio.run(
        app,
        host='0.0.0.0',
        port=PORT,
        ssl_context=(resource_path('cert.pem'), resource_path('key.pem')),
        allow_unsafe_werkzeug=True,
    )


def show_startup_dialog():
    """Desktop tip shown when the packaged EXE starts."""
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("AirMouse")
    root.resizable(False, False)
    root.attributes('-topmost', True)

    try:
        root.iconphoto(True, tk.PhotoImage(file=resource_path('static', 'app-icon.png')))
    except Exception:
        pass

    width, height = 420, 210
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 3
    root.geometry(f'{width}x{height}+{x}+{y}')
    root.configure(bg='#15151c')

    frame = tk.Frame(root, bg='#15151c', padx=28, pady=24)
    frame.pack(fill='both', expand=True)

    title_font = tkfont.Font(family='Microsoft YaHei UI', size=13, weight='bold')
    body_font = tkfont.Font(family='Microsoft YaHei UI', size=10)

    tk.Label(
        frame,
        text='AirMouse 已启动',
        font=title_font,
        fg='#ffffff',
        bg='#15151c',
        anchor='w',
    ).pack(fill='x')

    tk.Label(
        frame,
        text='请检查系统托盘，AirMouse 已在后台运行。\n之后可随时从托盘图标打开主页或扫码连接。',
        font=body_font,
        fg='#b0b0b8',
        bg='#15151c',
        justify='left',
        anchor='w',
        pady=(12, 22),
    ).pack(fill='x')

    buttons = tk.Frame(frame, bg='#15151c')
    buttons.pack(fill='x')

    def open_home():
        open_page('/')
        root.destroy()

    def dismiss():
        root.destroy()

    open_btn = tk.Button(
        buttons,
        text='打开网页',
        command=open_home,
        font=body_font,
        bg='#7b4dff',
        fg='#ffffff',
        activebackground='#6a3de6',
        activeforeground='#ffffff',
        relief='flat',
        padx=16,
        pady=8,
        cursor='hand2',
    )
    open_btn.pack(side='right')

    close_btn = tk.Button(
        buttons,
        text='知道了',
        command=dismiss,
        font=body_font,
        bg='#2a2a35',
        fg='#dddddd',
        activebackground='#3a3a48',
        activeforeground='#ffffff',
        relief='flat',
        padx=16,
        pady=8,
        cursor='hand2',
    )
    close_btn.pack(side='right', padx=(0, 10))

    root.protocol('WM_DELETE_WINDOW', dismiss)
    root.bind('<Escape>', lambda _event: dismiss())
    root.bind('<Return>', lambda _event: open_home())
    root.focus_force()
    root.mainloop()


def run_mac_menu_bar():
    """macOS 原生顶部菜单栏（NSStatusBar），0 额外内存开销，原生响应"""
    import gc
    import AppKit

    app = AppKit.NSApplication.sharedApplication()
    # 锁定 Accessory 模式：不占用 Dock 栏，但允许顶部菜单栏与窗口正常交互
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    # 检查并主动请求辅助功能权限
    is_trusted = True
    try:
        import ApplicationServices
        is_trusted = ApplicationServices.AXIsProcessTrusted()
        if not is_trusted:
            # 唤起系统设置授权提示并注册进辅助功能列表
            ApplicationServices.AXIsProcessTrustedWithOptions({'AXTrustedCheckOptionPrompt': True})
    except Exception:
        pass

    status_bar = AppKit.NSStatusBar.systemStatusBar()
    status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
    global _mac_status_item
    _mac_status_item = status_item

    button = status_item.button()
    icon_path = resource_path('static', 'menu-icon@2x.png')
    if not os.path.exists(icon_path):
        icon_path = resource_path('static', 'menu-icon.png')
    if not os.path.exists(icon_path):
        icon_path = resource_path('static', 'app-icon.png')

    if os.path.exists(icon_path):
        try:
            icon = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
            if icon:
                icon.setSize_(AppKit.NSMakeSize(18, 18))
                icon.setTemplate_(True)  # 设为 macOS 官方 Template 模式：透明背景、自适应纯色线框轮廓
                button.setImage_(icon)
            else:
                button.setTitle_('🖱️')
        except Exception:
            button.setTitle_('🖱️')
    else:
        button.setTitle_('🖱️')

    # 获取推荐局域网 IP
    try:
        targets = get_all_ip_addresses()
    except Exception:
        targets = []

    rec_ip = "127.0.0.1"
    for iface, ip in targets:
        if any(kw in iface.lower() for kw in ["en0", "en1", "wlan", "wi-fi"]):
            rec_ip = ip
            break

    connect_url = f"https://{rec_ip}:{PORT}/connect"

    class MacMenuTarget(AppKit.NSObject):
        def openConnect_(self, sender):
            open_page('/connect')

        def openHome_(self, sender):
            open_page('/')

        def openAccessibilitySettings_(self, sender):
            subprocess.run(['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'])

        def copyUrl_(self, sender):
            try:
                pasteboard = AppKit.NSPasteboard.generalPasteboard()
                pasteboard.clearContents()
                pasteboard.setString_forType_(connect_url, AppKit.NSPasteboardTypeString)
                subprocess.run([
                    'osascript', '-e',
                    'display notification "扫码连接地址已复制到剪贴板" with title "AirMouse"'
                ], capture_output=True)
            except Exception as e:
                print(f"copyUrl error: {e}")

        def quitApp_(self, sender):
            app.terminate_(None)
            os._exit(0)

    target = MacMenuTarget.alloc().init()
    global _mac_menu_target
    _mac_menu_target = target  # 保持全局引用防 Python 垃圾回收

    # 预先构建菜单项
    status_header = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f'🟢 AirMouse 运行中 (端口: {PORT})', None, ''
    )
    status_header.setEnabled_(False)

    ip_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        f'📍 本机 IP: {rec_ip}', None, ''
    )
    ip_item.setEnabled_(False)

    qr_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        '📷 打开扫码连接页 (二维码)', 'openConnect:', ''
    )
    qr_item.setTarget_(target)

    home_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        '🖥️ 打开电脑控制台', 'openHome:', ''
    )
    home_item.setTarget_(target)

    copy_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        '📋 复制手机扫码连接地址', 'copyUrl:', ''
    )
    copy_item.setTarget_(target)

    quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        '🚪 退出 AirMouse', 'quitApp:', 'q'
    )
    quit_item.setTarget_(target)

    menu = AppKit.NSMenu.alloc().init()

    # 动态代理：每次用户点击菜单栏图标展开菜单时，实时检测辅助功能权限并刷新菜单
    class MacMenuDelegate(AppKit.NSObject):
        def menuNeedsUpdate_(self, m):
            trusted_now = True
            try:
                import ApplicationServices
                trusted_now = ApplicationServices.AXIsProcessTrusted()
            except Exception:
                pass

            m.removeAllItems()

            if not trusted_now:
                warning_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    '⚠️ 辅助功能未生效 (点击去开启或重启应用)', 'openAccessibilitySettings:', ''
                )
                warning_item.setTarget_(target)
                m.addItem_(warning_item)
                m.addItem_(AppKit.NSMenuItem.separatorItem())

            m.addItem_(status_header)
            m.addItem_(ip_item)
            m.addItem_(AppKit.NSMenuItem.separatorItem())
            m.addItem_(qr_item)
            m.addItem_(home_item)
            m.addItem_(copy_item)
            m.addItem_(AppKit.NSMenuItem.separatorItem())
            m.addItem_(quit_item)

    menu_delegate = MacMenuDelegate.alloc().init()
    global _mac_menu_delegate
    _mac_menu_delegate = menu_delegate
    menu.setDelegate_(menu_delegate)

    # 初始填充一次
    menu_delegate.menuNeedsUpdate_(menu)

    status_item.setMenu_(menu)
    status_item.setHighlightMode_(True)

    # 在后台子线程启动 Flask-SocketIO 服务
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 启动 2 秒后执行一次垃圾回收整理内存
    def trim_memory():
        time.sleep(2.0)
        gc.collect()

    threading.Thread(target=trim_memory, daemon=True).start()

    # App 或首次启动时打开扫码页并提示
    if is_frozen() or os.environ.get('AIRMOUSE_AUTO_OPEN') == '1':
        def notify_start():
            if is_trusted:
                # 已经拥有辅助功能权限：正常延时打开扫码连接页
                time.sleep(0.8)
                open_page('/connect')
                subprocess.run([
                    'osascript', '-e',
                    'display notification "AirMouse 菜单栏已就绪，可随时从屏幕右上角扫码或管理" with title "AirMouse 已启动"'
                ], capture_output=True)
            else:
                # 首次启动未授权：绝不立即弹浏览器抢占焦点遮挡系统授权框！
                # 后台静默监听用户授权，授权完成后再自动唤起扫码页
                try:
                    import ApplicationServices
                    for _ in range(120):  # 轮询最多等待 60 秒
                        time.sleep(0.5)
                        if ApplicationServices.AXIsProcessTrusted():
                            time.sleep(0.4)
                            open_page('/connect')
                            subprocess.run([
                                'osascript', '-e',
                                'display notification "辅助功能权限已生效！已为您打开扫码连接页" with title "AirMouse 已就绪"'
                            ], capture_output=True)
                            return
                except Exception:
                    pass

        threading.Thread(target=notify_start, daemon=True).start()

    # 主线程进入 Cocoa 原生事件循环
    app.run()


def run_windows_tray():
    """Windows 原生任务栏系统托盘（pystray + Win32）"""
    import pystray
    from pystray import MenuItem as Item

    def on_open_home(icon, item):
        open_page('/')

    def on_open_qr(icon, item):
        open_page('/connect')

    def on_trust_cert(icon, item):
        threading.Thread(target=trust_ssl_certificate, daemon=True).start()

    def on_quit(icon, item):
        icon.stop()
        os._exit(0)

    menu = pystray.Menu(
        Item('打开主页', on_open_home, default=True),
        Item('扫码连接', on_open_qr),
        Item('信任 SSL 证书', on_trust_cert),
        Item('退出', on_quit),
    )
    icon = pystray.Icon('AirMouse', create_tray_image(), 'AirMouse 已在后台运行', menu)

    server = threading.Thread(target=start_server, daemon=True)
    server.start()

    # Keep tkinter on the main thread; run the tray icon beside it.
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()

    if is_frozen() or os.environ.get('AIRMOUSE_STARTUP_TIP') == '1':
        # Give the server a moment so “打开网页” is more likely to work immediately.
        time.sleep(0.8)
        try:
            show_startup_dialog()
        except Exception:
            pass

    tray_thread.join()


def run_with_tray():
    """跨平台托盘入口调度"""
    if platform.system() == 'Darwin':
        run_mac_menu_bar()
    else:
        run_windows_tray()


# --- SocketIO 事件绑定 ---

@socketio.on('connect')
def handle_connect():
    os_type = platform.system()
    socketio.emit('os_info', {'os': os_type})

@socketio.on('load_macros')
def handle_load():
    data = config_manager.load_macros()
    socketio.emit('macros_loaded', data)

@socketio.on('save_macros')
def handle_save(data):
    config_manager.save_macros(data)

@socketio.on('load_gp_macros')
def handle_gp_load():
    data = config_manager.load_gp_macros()
    socketio.emit('gp_macros_loaded', data)

@socketio.on('save_gp_macros')
def handle_gp_save(data):
    config_manager.save_gp_macros(data)
    gamepad_service.update_config(data)

@socketio.on('get_gamepads')
def handle_get_gps():
    gps = gamepad_service.get_gamepad_list()
    socketio.emit('gamepads_list', gps)

@socketio.on('select_gamepad')
def handle_select_gp(index):
    gamepad_service.selected_index = index
    handle_get_gps() # 刷新状态

# 鼠标事件
@socketio.on('move')
def on_move(data): mouse_service.handle_move(data)

@socketio.on('click')
def on_click(data): mouse_service.handle_click(data)

@socketio.on('drag_start')
def on_drag_start(): mouse_service.handle_drag_start()

@socketio.on('drag_end')
def on_drag_end(): mouse_service.handle_drag_end()

@socketio.on('mid_down')
def on_mid_down(): mouse_service.handle_mid_down()

@socketio.on('mid_up')
def on_mid_up(): mouse_service.handle_mid_up()

@socketio.on('scroll')
def on_scroll(data): mouse_service.handle_scroll(data)

# 键盘事件
@socketio.on('type_text')
def on_type(data): keyboard_service.handle_type_text(data)

@socketio.on('key_action')
def on_key(data): keyboard_service.handle_key_action(data)

@socketio.on('key_combo')
def on_combo(data): keyboard_service.handle_combo(data)

# ==========================================
# macOS 原生系统级手势底层支持 (CoreDock + Quartz HID)
# ==========================================
def _get_dock_notify():
    """获取 macOS 内部 CoreDock 通知接口，直通 Dock 守护进程"""
    try:
        import ctypes, ctypes.util
        app_services = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
        func = getattr(app_services, 'CoreDockSendNotification', None)
        if func:
            func.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            func.restype = None
            cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreFoundation'))
            cf.CFStringCreateWithCString.restype = ctypes.c_void_p
            cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
            def _notify(name):
                s = cf.CFStringCreateWithCString(None, name.encode('utf-8'), 0x08000100)
                func(s, None)
            return _notify
    except Exception:
        pass
    return None

_dock_notify = _get_dock_notify() if platform.system() == 'Darwin' else None

def mac_dock_action(notification_name, fallback_cmd=None):
    """直接调用 macOS Dock 内部机制触发系统手势，无按键冲突、无权限错误"""
    if _dock_notify:
        try:
            _dock_notify(notification_name)
            return True
        except Exception:
            pass
    if fallback_cmd:
        try:
            subprocess.Popen(fallback_cmd)
            return True
        except Exception:
            pass
    return False

def mac_switch_space(direction):
    """通过 Quartz HIDSystemState 硬件通道发送系统级切屏快捷键 (Ctrl + Left/Right)"""
    try:
        import Quartz
        key_code = 123 if direction == 'left' else 124
        CTRL_KEY = 59  # kVK_Control
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

        # 1. 发送 Control 键按下
        ctrl_d = Quartz.CGEventCreateKeyboardEvent(src, CTRL_KEY, True)
        Quartz.CGEventSetFlags(ctrl_d, Quartz.kCGEventFlagMaskControl)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ctrl_d)
        time.sleep(0.01)

        # 2. 发送 方向键按下 (带 Control 与 SecondaryFn 硬件标志，确保被 WindowServer 截获并执行切屏)
        arrow_flags = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskSecondaryFn
        arrow_d = Quartz.CGEventCreateKeyboardEvent(src, key_code, True)
        Quartz.CGEventSetFlags(arrow_d, arrow_flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, arrow_d)
        time.sleep(0.02)

        # 3. 发送 方向键抬起
        arrow_u = Quartz.CGEventCreateKeyboardEvent(src, key_code, False)
        Quartz.CGEventSetFlags(arrow_u, arrow_flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, arrow_u)
        time.sleep(0.01)

        # 4. 发送 Control 键抬起
        ctrl_u = Quartz.CGEventCreateKeyboardEvent(src, CTRL_KEY, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ctrl_u)
    except Exception as e:
        print(f"mac_switch_space error: {e}")

@socketio.on('system_gesture')
def on_system_gesture(data):
    action = data.get('action') if isinstance(data, dict) else str(data)
    is_mac = platform.system() == 'Darwin'
    if is_mac:
        if action == 'mission_control':
            # 调度中心 (全屏所有窗口展开)
            if not mac_dock_action('com.apple.expose.awake', ['open', '-a', 'Mission Control']):
                try:
                    subprocess.Popen(['open', '-a', 'Mission Control'])
                except Exception:
                    pass

        elif action in ('app_expose', 'swipe_down'):
            # 选项 1：纯正原生的 App Exposé (展开当前活跃软件的名下所有窗口)
            # 优先通过 Dock 内部机制直接触发，绝不发送干扰键盘的按键，绝无双发或权限1002错误
            if not mac_dock_action('com.apple.expose.front.awake'):
                # 备用方案：模拟 Ctrl + Down (带 SecondaryFn 标志)
                try:
                    import Quartz
                    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
                    ctrl_d = Quartz.CGEventCreateKeyboardEvent(src, 59, True)
                    Quartz.CGEventSetFlags(ctrl_d, Quartz.kCGEventFlagMaskControl)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ctrl_d)
                    time.sleep(0.01)
                    flags = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskSecondaryFn
                    down_d = Quartz.CGEventCreateKeyboardEvent(src, 125, True)
                    Quartz.CGEventSetFlags(down_d, flags)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_d)
                    time.sleep(0.02)
                    down_u = Quartz.CGEventCreateKeyboardEvent(src, 125, False)
                    Quartz.CGEventSetFlags(down_u, flags)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down_u)
                    time.sleep(0.01)
                    ctrl_u = Quartz.CGEventCreateKeyboardEvent(src, 59, False)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ctrl_u)
                except Exception:
                    pass

        elif action == 'space_left':
            # 切换到左侧空间 (桌面 / 全屏应用)
            mac_switch_space('left')

        elif action == 'space_right':
            # 切换到右侧空间 (桌面 / 全屏应用)
            mac_switch_space('right')

        elif action == 'show_desktop':
            # 显示桌面
            mac_dock_action('com.apple.showdesktop.awake')

        elif action == 'launchpad':
            # 启动台
            if not mac_dock_action('com.apple.launchpad.toggle', ['open', '-a', 'Launchpad']):
                try:
                    subprocess.Popen(['open', '-a', 'Launchpad'])
                except Exception:
                    pass
    else:
        # Windows 对应手势
        if action == 'mission_control':
            keyboard_service.handle_combo({'keys': ['win', 'tab']})
        elif action in ('show_desktop', 'app_expose', 'swipe_down'):
            keyboard_service.handle_combo({'keys': ['win', 'd']})
        elif action == 'space_left':
            keyboard_service.handle_combo({'keys': ['ctrl', 'win', 'left']})
        elif action == 'space_right':
            keyboard_service.handle_combo({'keys': ['ctrl', 'win', 'right']})

def mac_post_cmd_key(keycode):
    """在 macOS 上发送 Command + 对应键"""
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        kd = Quartz.CGEventCreateKeyboardEvent(src, keycode, True)
        Quartz.CGEventSetFlags(kd, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, kd)
        time.sleep(0.01)
        ku = Quartz.CGEventCreateKeyboardEvent(src, keycode, False)
        Quartz.CGEventSetFlags(ku, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ku)
    except Exception as e:
        print(f"mac_post_cmd_key error: {e}")

@socketio.on('zoom')
def on_zoom(data):
    # 双指缩放：放大 / 缩小 (零延迟、零卡顿、无阻塞)
    direction = data.get('direction', 'in') if isinstance(data, dict) else 'in'
    is_mac = platform.system() == 'Darwin'
    if is_mac:
        try:
            import Quartz
            src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
            # 触发原生通用缩放快捷键：放大 Cmd + '=' (key 24); 缩小 Cmd + '-' (key 27)
            keycode = 24 if direction == 'in' else 27
            kd = Quartz.CGEventCreateKeyboardEvent(src, keycode, True)
            Quartz.CGEventSetFlags(kd, Quartz.kCGEventFlagMaskCommand)
            ku = Quartz.CGEventCreateKeyboardEvent(src, keycode, False)
            Quartz.CGEventSetFlags(ku, Quartz.kCGEventFlagMaskCommand)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, kd)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ku)
        except Exception as e:
            print(f"zoom error: {e}")
    else:
        # Windows: Ctrl + '+' / Ctrl + '-'
        key = '+' if direction == 'in' else '-'
        keyboard_service.handle_combo({'keys': ['ctrl', key]})

@socketio.on('rotate')
def on_rotate(data):
    # 双指旋转：顺时针 / 逆时针
    direction = data.get('direction', 'right') if isinstance(data, dict) else 'right'
    is_mac = platform.system() == 'Darwin'
    if is_mac:
        # 顺时针旋转: Cmd + R (key 15); 逆时针旋转: Cmd + L (key 37)
        # 适用于预览(Preview)、访达空格预览、照片(Photos)等原生看图与设计软件
        keycode = 15 if direction == 'right' else 37
        mac_post_cmd_key(keycode)
    else:
        # Windows 对应旋转 (如画图/看图工具 Ctrl + R)
        key = 'r' if direction == 'right' else 'l'
        keyboard_service.handle_combo({'keys': ['ctrl', key]})

@socketio.on('smart_zoom')
def on_smart_zoom():
    # 双指双击：智能缩放重置 (Cmd + 0)
    is_mac = platform.system() == 'Darwin'
    if is_mac:
        mac_post_cmd_key(29) # key 29 = '0'
    else:
        keyboard_service.handle_combo({'keys': ['ctrl', '0']})

def check_already_running():
    """检测端口是否已被占用，防止重复启动崩溃并直接唤起扫码页"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            if s.connect_ex(('127.0.0.1', PORT)) == 0:
                webbrowser.open(f'https://127.0.0.1:{PORT}/connect')
                if platform.system() == 'Darwin':
                    subprocess.run([
                        'osascript', '-e',
                        'display notification "AirMouse 已在后台运行，已为您打开扫码连接页" with title "AirMouse"'
                    ], capture_output=True)
                sys.exit(0)
    except Exception:
        pass

if __name__ == '__main__':
    check_already_running()

    use_tray = os.environ.get('AIRMOUSE_NO_TRAY') != '1'
    hide_console = os.environ.get('AIRMOUSE_SHOW_CONSOLE') != '1'

    if hide_console:
        hide_console_window()

    if use_tray:
        try:
            run_with_tray()
            sys.exit(0)
        except Exception as e:
            print(f"Tray error: {e}, falling back to console mode")
            pass

    ips = get_all_ip_addresses()

    print("\n" + "═"*60)
    print("🚀 Remote Pro Server 已启动！")
    print(f"🏠 当前系统: {platform.system()}")
    print("📱 请在浏览器访问以下地址:")
    print(f"🖥️  本机主页: https://127.0.0.1:{PORT}/")
    print(f"📷  扫码连接: https://127.0.0.1:{PORT}/connect")

    for interface, ip in ips:
        tag = ""
        if any(keyword in interface.lower() for keyword in ["wlan", "wi-fi", "eth", "en0", "en1"]):
            tag = " [推荐]"
        print(f"  ➤  https://{ip}:{PORT}{tag}")

    print("═"*60 + "\n")

    # App 模式下启动后自动打开扫码连接网页
    def auto_open_browser():
        time.sleep(1.0)
        try:
            webbrowser.open(f'https://127.0.0.1:{PORT}/connect')
            if platform.system() == 'Darwin':
                subprocess.run([
                    'osascript', '-e',
                    'display notification "服务已就绪，请使用手机扫描屏幕二维码连接" with title "AirMouse 已启动"'
                ], capture_output=True)
        except Exception as e:
            print(f"auto_open_browser error: {e}")

    if is_frozen() or os.environ.get('AIRMOUSE_AUTO_OPEN') == '1':
        threading.Thread(target=auto_open_browser, daemon=True).start()

    start_server()
