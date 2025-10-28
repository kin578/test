# theme.py
# 목적: 앱 전체에 "py_dracula_dark.qss" (+ 있으면 "py_dracula_dark_overlay.qss")를 항상 적용.
# 사용: QApplication 만든 뒤, set_theme(app) 한 줄이면 끝.

from __future__ import annotations
from pathlib import Path
from typing import Iterable, Optional
from PySide6.QtCore import QFile
from PySide6.QtWidgets import QApplication

# QSS를 찾을 후보 경로들(위에서부터 순서대로 검사)
BASE_CANDIDATES = [
    "py_dracula_dark.qss",                   # 프로젝트 루트
    "themes/py_dracula_dark.qss",            # ./themes/
    ":/themes/py_dracula_dark.qss",          # 리소스(:/themes/…)
    "vendor/pydracula/themes/py_dracula_dark.qss",  # 벤더 폴더(있을 때만)
]
OVERLAY_CANDIDATES = [
    "py_dracula_dark_overlay.qss",
    "themes/py_dracula_dark_overlay.qss",
    ":/themes/py_dracula_dark_overlay.qss",
    "vendor/pydracula/themes/py_dracula_dark_overlay.qss",
]

# 우리 앱 프레임/제목바/카드/메뉴바에 얕게 덮어쓸 보강 QSS
FRAME_QSS = """
/* 프레임(바깥 카드)와 제목바/메뉴/버튼을 Dracula 팔레트 톤으로 맞춘다 */
QMainWindow { background: transparent; }
QWidget#root { background: transparent; }

QWidget#card {
    background: palette(base);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
}

/* 메뉴바(좌측) */
QMenuBar#menubar { background: transparent; border: none; }
QMenuBar#menubar::item { padding: 6px 10px; margin: 4px 6px; border-radius: 8px; }
QMenuBar#menubar::item:selected { background: rgba(255,255,255,0.06); }

/* 제목바 버튼(우측) */
QToolButton#btnMin, QToolButton#btnMax, QToolButton#btnClose {
    min-width: 36px;  max-width: 36px;
    min-height: 36px; max-height: 36px;
    font-size: 18px;
    border: 1px solid rgba(255,255,255,0.18);
    background: rgba(255,255,255,0.05);
    color: palette(button-text);
    border-radius: 12px;
}
QToolButton#btnMin:hover, QToolButton#btnMax:hover { background: rgba(255,255,255,0.12); }
QToolButton#btnClose:hover { background: rgba(255,80,80,0.28); }

/* 탭 영역 살짝 */
QTabBar::tab { padding: 7px 12px; margin: 6px 6px 0 0; border-radius: 10px; background: rgba(255,255,255,0.04); }
QTabBar::tab:selected { background: rgba(255,255,255,0.10); }
QTabWidget::pane { border: none; top: 6px; }

/* 상태바 */
QStatusBar#status { background: transparent; border-top: 1px solid rgba(255,255,255,0.06); padding: 6px 4px; }
"""

def _read_fs_text(path: Path) -> Optional[str]:
    """일반 파일을 UTF-8로 읽는다. 실패하면 None."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

def _read_qrc_text(qrc_path: str) -> Optional[str]:
    """QResource(:/...) 경로에서 텍스트를 읽는다. 실패하면 None."""
    try:
        f = QFile(qrc_path)
        if not (f.exists() and f.open(QFile.ReadOnly | QFile.Text)):
            return None
        try:
            return bytes(f.readAll()).decode("utf-8", "ignore")
        finally:
            f.close()
    except Exception:
        return None

def _read_first_qss(candidates: Iterable[str]) -> str:
    """
    후보 경로 리스트에서 가장 먼저 성공적으로 읽히는 QSS 내용을 반환.
    하나도 없으면 빈 문자열.
    """
    for p in candidates:
        if p.startswith(":/"):  # QRC
            data = _read_qrc_text(p)
            if data and data.strip():
                return data
        else:                    # 파일시스템
            data = _read_fs_text(Path(p))
            if data and data.strip():
                return data
    return ""

def _apply_qss(app: QApplication, base_css: str, overlay_css: str) -> None:
    """
    base_css가 비어있으면 아무 것도 하지 않음(앱은 기본 스타일로 뜸).
    base + overlay를 합쳐서 한 번에 setStyleSheet.
    """
    if not base_css.strip():
        return
    css = base_css if not overlay_css.strip() else (base_css + "\n\n" + overlay_css)
    try:
        # 동일 CSS로 재적용하면 깜빡임만 생기니, 변화 있을 때만 적용
        if app.styleSheet() != css:
            app.setStyleSheet(css)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────
# 외부에서 쓰는 API 시그니처 유지(네 기존 코드와 호환)
def set_theme(app: QApplication, mode: str = "dark") -> None:
    """
    예전처럼 set_theme(app, "dark"/"light"…)로 호출돼도
    내부에서는 py_dracula_dark.qss를 '항상' 적용하고,
    우리 프레임 전용 QSS(FRAME_QSS)도 끝에 덧입힌다.
    """
    base = _read_first_qss(BASE_CANDIDATES)
    overlay = _read_first_qss(OVERLAY_CANDIDATES)

    # overlay 뒤에 우리 프레임 보강 QSS를 추가
    overlay_plus = (overlay + "\n\n" if overlay.strip() else "") + FRAME_QSS

    _apply_qss(app, base, overlay_plus)

def apply_overlay(app: QApplication, *_, **__) -> None:
    """
    과거엔 오버레이 전용이었을 수 있지만,
    지금은 호출돼도 결과적으로 '다크 QSS 고정'을 다시 보장한다.
    """
    set_theme(app)

def clear_theme(target) -> None:
    """
    테마 해제를 시도해도 최종 결과는 '다크 유지'.
    - target이 QApplication이면 그대로 set_theme(target)
    - 위젯이면 QApplication.instance()에 재적용
    """
    from PySide6.QtWidgets import QApplication as _QApp
    if isinstance(target, _QApp):
        set_theme(target)
    else:
        app = _QApp.instance()
        if app is not None:
            set_theme(app)
