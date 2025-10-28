# lux_theme.py
# PySide6 전용 고급 테마 유틸 (라이트/다크 + 포인트 컬러 + QSS)
from __future__ import annotations
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def _qcolor(hex_or_tuple) -> QColor:
    if isinstance(hex_or_tuple, (tuple, list)) and len(hex_or_tuple) in (3, 4):
        return QColor(*hex_or_tuple)
    return QColor(str(hex_or_tuple))


def _make_palette(mode: str, base: str, on_base: str, panel: str) -> QPalette:
    pal = QPalette()

    c_base   = _qcolor(base)      # 기본 바탕
    c_panel  = _qcolor(panel)     # 패널/카드 바탕
    c_text   = _qcolor(on_base)   # 기본 글자
    c_muted  = QColor(130, 138, 148) if mode == "dark" else QColor(90, 98, 110)
    c_alt    = QColor(20, 22, 25) if mode == "dark" else QColor(245, 246, 248)

    pal.setColor(QPalette.Window,         c_panel)
    pal.setColor(QPalette.WindowText,     c_text)
    pal.setColor(QPalette.Base,           c_base)
    pal.setColor(QPalette.AlternateBase,  c_alt)
    pal.setColor(QPalette.ToolTipBase,    c_panel)
    pal.setColor(QPalette.ToolTipText,    c_text)
    pal.setColor(QPalette.Text,           c_text)
    pal.setColor(QPalette.Button,         c_panel)
    pal.setColor(QPalette.ButtonText,     c_text)
    pal.setColor(QPalette.BrightText,     QColor("#ff4d4f"))
    pal.setColor(QPalette.Disabled, QPalette.Text, c_muted)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, c_muted)
    pal.setColor(QPalette.Highlight, QColor("#3b82f6"))  # 선택 배경(파랑)
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    return pal


def _build_qss(accent: str, radius: int, mode: str) -> str:
    # drop-shadow는 QSS로 직접 못 넣어서, 그림자 느낌은 테두리/배경 대비로 표현
    bg_panel   = "#0f172a" if mode == "dark" else "#ffffff"
    bg_base    = "#0b1220" if mode == "dark" else "#f7f8fa"
    border_col = "#233147" if mode == "dark" else "#e6e8ec"
    hover_bg   = "#1b263b" if mode == "dark" else "#eef3ff"
    press_bg   = "#162033" if mode == "dark" else "#dfe9ff"
    text_muted = "#9aa4b2" if mode == "dark" else "#6b7280"

    return f"""
    * {{
        font-family: "Noto Sans", "Malgun Gothic", "Apple SD Gothic Neo", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        font-size: 13px;
    }}
    QWidget {{
        background: {bg_panel};
        color: #e5e7eb;
    }}
    QLabel[muted="true"] {{
        color: {text_muted};
    }}
    QGroupBox {{
        border: 1px solid {border_col};
        border-radius: {radius}px;
        margin-top: 10px;
        padding: 8px 10px 10px 10px;
        background: {bg_panel};
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit, QComboBox {{
        background: {bg_base};
        border: 1px solid {border_col};
        border-radius: {radius}px;
        padding: 6px 8px;
        selection-background-color: {accent};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus, QComboBox:focus {{
        border: 1px solid {accent};
        outline: none;
    }}
    QComboBox::drop-down {{
        width: 24px;
        border: none;
    }}

    QPushButton {{
        background: {bg_base};
        border: 1px solid {border_col};
        padding: 6px 12px;
        border-radius: {radius}px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {hover_bg}; }}
    QPushButton:pressed {{ background: {press_bg}; }}
    QPushButton[primary="true"] {{
        background: {accent};
        color: #ffffff;
        border: 1px solid {accent};
    }}
    QPushButton[primary="true"]:hover {{
        filter: brightness(1.05);
    }}
    QPushButton[danger="true"] {{
        background: #ef4444; color: #fff; border: 1px solid #ef4444;
    }}

    QTableView, QTableWidget {{
        background: {bg_base};
        gridline-color: {border_col};
        border: 1px solid {border_col};
        border-radius: {radius}px;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QHeaderView::section {{
        background: {bg_panel};
        color: #e5e7eb;
        border: 1px solid {border_col};
        padding: 6px;
    }}
    QTableCornerButton::section {{
        background: {bg_panel};
        border: 1px solid {border_col};
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px; height: 18px;
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {accent};
        border: 1px solid {accent};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {border_col};
        border-radius: 6px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {accent};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 12px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {border_col};
        border-radius: 6px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {accent};
    }}

    QToolTip {{
        background: {bg_base};
        color: #e5e7eb;
        border: 1px solid {border_col};
        border-radius: {radius}px;
        padding: 6px 8px;
    }}
    """


def apply_theme(app: QApplication, mode: str = "dark", accent: str = "#6366f1", corner_radius: int = 10) -> None:
    """
    app 전체에 테마 적용 (라이트/다크 + 포인트 색상 변경 가능)
    - mode: "dark" | "light"
    - accent: 포인트 색상 (hex)
    - corner_radius: 둥근 모서리 픽셀
    """
    mode = (mode or "dark").lower()
    if mode not in ("dark", "light"):
        mode = "dark"

    if mode == "dark":
        pal = _make_palette("dark", base="#0b1220", on_base="#e5e7eb", panel="#0f172a")
    else:
        pal = _make_palette("light", base="#f7f8fa", on_base="#111827", panel="#ffffff")

    app.setPalette(pal)
    app.setStyleSheet(_build_qss(accent=accent, radius=int(corner_radius), mode=mode))
