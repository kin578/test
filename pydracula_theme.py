from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QApplication

# 우리가 고정해서 쓸 QSS 파일명
_DARK_QSS_FILES = [
    "py_dracula_dark.qss",
    "vendor/pydracula/themes/py_dracula_dark.qss",  # 혹시 이 경로에 둘 수도 있으니 후보로 둡니다
]

def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None

def set_theme(app: QApplication, mode: str = "dark") -> None:
    """
    기존 코드에서 set_theme(app, "dark"|"light"|"clear")로 호출하더라도
    '무조건' py_dracula_dark.qss 를 적용합니다. (테마 고정!)
    """
    for p in _DARK_QSS_FILES:
        qss_path = Path(p)
        if qss_path.exists():
            qss = _read_text(qss_path)
            if qss:
                app.setStyleSheet(qss)
                return
    # 만약 못 찾으면 그냥 조용히 지나가기 (앱은 계속 동작)
