from __future__ import annotations

# (선택) 크래시 감시자 — 없으면 조용히 패스
try:
    from crash_guard import arm_crash_watchdog
    arm_crash_watchdog("Equipment Manager")
except Exception:
    pass

import os
import sys
import subprocess
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

# ─────────────────────────────────────────────────────────
# PyInstaller(EXE) 실행 시, 작업폴더를 실행 파일 위치로 고정(상대경로 혼동 방지)
if getattr(sys, "frozen", False):
    try:
        os.chdir(os.path.dirname(sys.executable))
    except Exception:
        pass

# 콘솔 한글 깨짐 방지(가능한 환경에서만)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Qt/3rd 로그 소음 줄이기
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false;qt.*.debug=false;qt.*.info=false;qt.*.warning=false")

def _setup_logging() -> None:
    """logs/app.log 로 순환 로깅(1MB x 3개). 실패해도 앱은 계속."""
    try:
        d = Path("logs"); d.mkdir(exist_ok=True)
        h = RotatingFileHandler(d / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        if not any(isinstance(x, RotatingFileHandler) for x in root.handlers):
            root.addHandler(h)
        if root.level == logging.NOTSET:
            root.setLevel(logging.INFO)
    except Exception:
        pass

# 개발 중 QRC 자동 컴파일(resources.qrc → resources_rc.py)
def _ensure_local_qrc() -> bool:
    try:
        import resources_rc  # noqa: F401
        return True
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        return False
    qrc = Path("resources.qrc"); py = Path("resources_rc.py")
    if not qrc.exists():
        return False
    for cmd in (
        [sys.executable, "-m", "PySide6.scripts.pyside_tool", "rcc", str(qrc), "-o", str(py)],
        ["pyside6-rcc", str(qrc), "-o", str(py)],
        ["pyrcc6", str(qrc), "-o", str(py)],
    ):
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            import importlib, resources_rc  # type: ignore
            importlib.reload(resources_rc)
            return True
        except Exception:
            continue
    return False

_ = _setup_logging()
_ = _ensure_local_qrc()

# ─────────────────────────────────────────────────────────
# Qt import는 QRC 준비 후에
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QLineEdit, QMessageBox, QTabWidget
from PySide6.QtGui import QIcon
from PySide6.QtCore import QTimer, QFile, Qt, QTranslator, QLocale, QLibraryInfo

# 메인 UI
from ui.main_window import MainWindow, bootstrap

# ★ 테마: 루트(theme.py) 또는 ui/theme.py 어느 쪽이든 불러오게
try:
    from theme import set_theme, apply_overlay            # 루트에 theme.py가 있을 때
except ImportError:
    from ui.theme import set_theme, apply_overlay         # ui/theme.py에 있을 때

# 파일 대화상자 커스텀(올 커스텀 유지)
from ui.file_dialog_patch import enable_file_dialog_fix

def _apply_app_identity(app: QApplication):
    """앱 이름/아이콘/작업표시줄 그룹화 ID 설정."""
    app.setApplicationName("Equipment Manager")
    app.setOrganizationName("DeskApp")
    app.setOrganizationDomain("deskapp.local")
    for p in ("assets/icons/app.ico", "assets/icons/app.png", "icon.ico", "icon.png"):
        if Path(p).exists():
            app.setWindowIcon(QIcon(p))
            break
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DeskApp.EquipmentManager")
    except Exception:
        pass

def _install_korean_translations(app: QApplication):
    """Qt 기본 문구 한글화(파일창 버튼 등). 없어도 앱은 정상."""
    try:
        tr = QTranslator()
        try:
            tr_path = QLibraryInfo.path(QLibraryInfo.TranslationsPath)
        except Exception:
            tr_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath) if hasattr(QLibraryInfo, "location") else ""
        for base in ("qtbase", "qt"):
            if tr.load(QLocale("ko_KR"), base, "_", tr_path):
                app.installTranslator(tr)
                break
    except Exception:
        pass

def _patch_combobox_arrow(app: QApplication):
    """
    콤보박스 ▼ 아이콘(QRC → 로컬 폴백) 자동 적용.
    아이콘이 없어도 조용히 스킵(앱은 그대로 동작).
    """
    qrc = [
        ":/icons/images/icons/cil-arrow-bottom-2.png",
        ":/icons/images/icons/cil-arrow-bottom.png",
        ":/images/icons/cil-arrow-bottom-2.png",
        ":/images/icons/cil-arrow-bottom.png",
    ]
    fs = [
        "images/icons/cil-arrow-bottom-2.png",
        "images/icons/cil-arrow-bottom.png",
        "icons/images/icons/cil-arrow-bottom-2.png",
        "icons/images/icons/cil-arrow-bottom.png",
        "vendor/pydracula/images/icons/cil-arrow-bottom-2.png",
        "vendor/pydracula/images/icons/cil-arrow-bottom.png",
    ]
    url = None
    for p in qrc:
        try:
            if QFile.exists(p):
                url = p; break
        except Exception:
            pass
    if url is None:
        for p in fs:
            if Path(p).exists():
                url = p; break
    if url is None:
        return
    qss = f"""
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: 1px solid rgba(255,255,255,0.12);
    }}
    QComboBox::down-arrow {{
        image: url({url});
        width: 12px; height: 12px;
    }}
    """
    try:
        app.setStyleSheet((app.styleSheet() or "") + qss)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 앱 초기 준비(네 기존 bootstrap 흐름 존중)
    bootstrap()

    app = QApplication(sys.argv)
    _install_korean_translations(app)
    _apply_app_identity(app)

    # ★★★ 여기서 '무조건' 다크 QSS 적용(파일에서 자동 탐색) ★★★
    set_theme(app)         # py_dracula_dark.qss 고정 적용
    apply_overlay(app)     # 오버레이 파일이 있으면 얹음(없으면 조용히 스킵)

    # 파일 대화상자: 네가 '올 커스텀' 원한다고 했으니 활성화 유지
    # (나중에 윈도우 기본으로 돌리고 싶으면 아래 줄을 주석 처리)
    enable_file_dialog_fix()

    # ▼ 콤보박스 ▼ 아이콘 보정(QRC → 로컬 폴백)
    _patch_combobox_arrow(app)

    # 로그인(있을 때만)
    have_auth = True
    try:
        from ui.dialogs.login_dialog import LoginDialog
        import user_session
        from services.audit_log import log_event
    except Exception:
        have_auth = False
        user_session = None
        def log_event(*args, **kwargs): pass

    if have_auth:
        dlg = LoginDialog()
        if dlg.exec() != QDialog.Accepted:
            sys.exit(0)
        try:
            u = user_session.get_current_user()
            log_event("app_start", "application started", user=(u.name if u else None))
        except Exception:
            pass
    else:
        # (폴백) 임시 로그인
        name, ok = QInputDialog.getText(None, "로그인(임시)", "이름:", QLineEdit.Normal)
        if not ok or not name:
            sys.exit(0)
        pw, ok = QInputDialog.getText(None, "비밀번호(임시)", "비밀번호:", QLineEdit.Password)
        if not ok or pw != "1234":
            QMessageBox.critical(None, "오류", "로그인 실패")
            sys.exit(0)

    # 메인 윈도우
    w = MainWindow()
    w.resize(1200, 700)
    if not app.windowIcon().isNull():
        w.setWindowIcon(app.windowIcon())
    w.show()

    # (선택) 추가 시각효과가 필요하면 여기에 타이머로 연결 가능
    # QTimer.singleShot(1, lambda: some_overlay_effect())

    sys.exit(app.exec())
