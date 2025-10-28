# no_white_theme.py
# 목적: 앱 전체에서 눈부신 순백색을 억제(다크 팔레트 + 약한 QSS)하되,
#       파일 대화상자(QFileDialog)는 "네이티브(윈도우 기본)" 그대로 사용하도록 한다.
#
# 중요: 예전 버전에서 하던 "QFileDialog 강제 커스텀화(DontUseNativeDialog 등 몽키패치)"는
#       전부 제거했다. (이 모듈은 절대 파일 대화상자 옵션을 건드리지 않는다.)

from __future__ import annotations
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication


def _apply_dark_palette(app: QApplication) -> None:
    p = QPalette()

    # 기본 톤
    window = QColor(33, 33, 38)      # 전체 배경
    base   = QColor(27, 27, 31)      # 입력창/패널 내부
    alt    = QColor(38, 38, 44)      # 테이블 교차행 등
    text   = QColor(232, 232, 236)   # 본문 텍스트
    subtx  = QColor(180, 180, 188)   # 보조 텍스트
    disab  = QColor(120, 120, 128)   # 비활성 텍스트
    btnbg  = QColor(41, 41, 48)      # 버튼
    link   = QColor(130, 165, 255)

    # 창/기본
    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, alt)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, btnbg)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor(255, 72, 72))
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Link, link)
    p.setColor(QPalette.Highlight, QColor(72, 119, 255))
    p.setColor(QPalette.HighlightedText, QColor(245, 245, 248))

    # 비활성 상태
    p.setColor(QPalette.Disabled, QPalette.WindowText, disab)
    p.setColor(QPalette.Disabled, QPalette.Text, disab)
    p.setColor(QPalette.Disabled, QPalette.ButtonText, disab)
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor(70, 70, 78))
    p.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(190, 190, 196))

    app.setPalette(p)


# 부드러운 기본 위젯 룩을 위한 얕은 QSS (눈부신 흰색 제거 + 테두리 살짝)
_QSS = """
/* 공통 */
QWidget { background: palette(window); color: palette(window-text); }
QFrame, QGroupBox, QTabWidget::pane {
    background: palette(window);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 2px 4px; }

/* 입력 */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit, QComboBox, QListView, QTableView, QTreeView {
    background: palette(base);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: palette(disabled, text);
}

/* 버튼 */
QPushButton {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px;
    padding: 6px 10px;
}
QPushButton:hover { background: rgba(255,255,255,0.12); }
QPushButton:pressed { background: rgba(255,255,255,0.18); }

/* 테이블 */
QHeaderView::section {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.10);
    padding: 4px 6px;
}
QTableView {
    gridline-color: rgba(255,255,255,0.10);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}

/* 상태바/툴팁 */
QStatusBar { background: transparent; }
QToolTip {
    background-color: rgba(20,20,24,0.96);
    color: palette(window-text);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 6px;
    padding: 6px 8px;
}
"""


def apply_no_white_theme(app: QApplication, *args, **kwargs) -> None:
    """
    앱 전역에 '흰색 최소화' 다크 팔레트/얕은 QSS를 적용한다.
    - QFileDialog 네이티브 여부에는 절대 간섭하지 않는다.
    - 예전 버전에서 하던 'DontUseNativeDialog' 강제 패치/몽키패치는 전부 삭제했다.

    인자(*args, **kwargs)는 하위호환을 위해 받지만 사용하지 않는다.
    """
    # 1) 다크 팔레트
    _apply_dark_palette(app)

    # 2) 얕은 QSS (기존 스타일시트 위에 덮되, 전역을 해치지 않는 선)
    try:
        app.setStyleSheet((app.styleSheet() or "") + "\n" + _QSS)
    except Exception:
        # 스타일시트가 적용 불가해도 오류로 중단하지 않음
        pass

    # 3) (의도적으로 없음) QFileDialog 커스텀 패치 금지
    #    - 여기서 네이티브/커스텀을 절대 건드리지 않는다.
    #    - Qt.AA_DontUseNativeDialogs 같은 전역 속성도 여기서는 절대 설정하지 않는다.
