# crash_guard.py
from __future__ import annotations
import os, sys, traceback, datetime, faulthandler, threading

LOG_DIR = "logs"

def _ensure_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception:
        pass

def _write_log(text: str) -> str:
    _ensure_dir()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"crash_{ts}.log")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        with open(os.path.join(LOG_DIR, "last_crash.log"), "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        pass
    return path

def _messagebox(title: str, text: str):
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, title, text)
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # MB_ICONHAND
    except Exception:
        pass

def _excepthook(tp, value, tb):
    msg = "".join(traceback.format_exception(tp, value, tb))
    path = _write_log(msg)
    short = (msg[-2000:] if len(msg) > 2000 else msg)
    _messagebox("치명적 오류", f"프로그램이 예기치 않게 종료되었습니다.\n\n로그: {path}\n\n{short}")
    try:
        sys.__excepthook__(tp, value, tb)
    except Exception:
        pass

def _thread_excepthook(args):
    _excepthook(args.exc_type, args.exc_value, args.exc_traceback)

def arm_crash_watchdog(app_name: str = "DeskApp"):
    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass
    try:
        sys.stderr = sys.__stderr__
    except Exception:
        pass
    sys.excepthook = _excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _thread_excepthook
    # 필요 시: set DESKAPP_QT_DEBUG=1 로 Qt 플러그인 디버그
    if os.getenv("DESKAPP_QT_DEBUG", "0") == "1":
        os.environ["QT_DEBUG_PLUGINS"] = "1"
