import os
import sys
import shutil
import platform


def is_frozen():
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def resource_dir():
    """Read-only bundled resources (templates / static / certs)."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def app_dir():
    """Writable directory next to the exe, or user app support in macOS .app bundle, or project root in source mode."""
    if is_frozen():
        if platform.system() == 'Darwin':
            cfg_dir = os.path.expanduser('~/Library/Application Support/AirMouse')
            os.makedirs(cfg_dir, exist_ok=True)
            for fname in ('macro_configs.json', 'gamepad_configs.json'):
                target = os.path.join(cfg_dir, fname)
                if not os.path.exists(target):
                    src = os.path.join(resource_dir(), fname)
                    if os.path.exists(src):
                        try:
                            shutil.copy2(src, target)
                        except Exception:
                            pass
            return cfg_dir
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts):
    return os.path.join(resource_dir(), *parts)


def app_path(*parts):
    return os.path.join(app_dir(), *parts)
