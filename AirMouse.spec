# -*- mode: python ; coding: utf-8 -*-
import sys
import platform

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('cert.pem', '.'),
    ('key.pem', '.'),
    ('macro_configs.json', '.'),
    ('gamepad_configs.json', '.')
]

hiddenimports = [
    'engineio.async_drivers.threading',
    'flask_socketio',
    'socketio',
    'engineio',
    'simple_websocket',
    'wsproto',
    'pynput',
    'psutil',
    'PIL',
    'cryptography'
]

a = Analysis(
    ['server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AirMouse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['build/AppIcon.icns'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AirMouse',
)

info_plist = {
    'CFBundleDisplayName': 'AirMouse',
    'CFBundleName': 'AirMouse',
    'CFBundleIdentifier': 'com.yhgao99.airmouse',
    'CFBundleVersion': '1.0.0',
    'CFBundleShortVersionString': '1.0.0',
    'NSHighResolutionCapable': True,
    'NSRequiresAquaSystemAppearance': False,
    'NSAccessibilityUsageDescription': 'AirMouse 需要辅助功能权限以模拟鼠标移动、手势控制与键盘按键输入。',
    'NSAppleEventsUsageDescription': 'AirMouse 需要系统控制权限以触发窗口调度与手势切换。',
}

app = BUNDLE(
    coll,
    name='AirMouse.app',
    icon='build/AppIcon.icns',
    bundle_identifier='com.yhgao99.airmouse',
    info_plist=info_plist,
)
