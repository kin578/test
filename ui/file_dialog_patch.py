# ui/file_dialog_patch.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QFile, QSize, QEvent, QPoint
from PySide6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QToolButton, QLabel,
    QHBoxLayout, QVBoxLayout, QGridLayout, QBoxLayout,
    QStyle, QPushButton
)

# ──────────────────────────────
# 유틸: 아이콘 탐색(QRC → 로컬 폴백)
def _find_icon(filename: str) -> Optional[str]:
    qrc = [
        f":/icons/images/icons/{filename}",
        f":/images/icons/{filename}",
        f":/images/{filename}",
    ]
    fs = [
        f"icons/images/icons/{filename}",
        f"images/icons/{filename}",
        f"images/{filename}",
        f"vendor/pydracula/images/icons/{filename}",
    ]
    for p in qrc:
        try:
            if QFile.exists(p):
                return p
        except Exception:
            pass
    for p in fs:
        if Path(p).exists():
            return str(Path(p).as_posix())
    return None

def _arrow_url() -> Optional[str]:
    for name in ("cil-arrow-bottom-2.png", "cil-arrow-bottom.png", "arrow-down.png"):
        u = _find_icon(name)
        if u:
            return u
    return None


# ──────────────────────────────
# 전용 QSS (파일 다이얼로그 내부 + 콤보박스 화살표)
def _file_dialog_qss() -> str:
    arrow = _arrow_url() or ""
    return f"""
    QFileDialog, QFileDialog QWidget {{
        background: palette(window);
        color: palette(window-text);
    }}
    QFileDialog QFrame, QFileDialog QGroupBox {{
        background: palette(window);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
    }}
    QFileDialog QLineEdit, QFileDialog QComboBox, QFileDialog QSpinBox, QFileDialog QDoubleSpinBox {{
        background: palette(base);
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 6px;
        padding: 4px 6px;
    }}
    QFileDialog QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 22px;
        border-left: 1px solid rgba(255,255,255,0.12);
    }}
    QFileDialog QComboBox::down-arrow {{
        image: url({arrow});
        width: 12px; height: 12px;
    }}
    QFileDialog QPushButton {{
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 8px;
        padding: 6px 10px;
    }}
    QFileDialog QPushButton:hover {{ background: rgba(255,255,255,0.12); }}
    QFileDialog QPushButton:pressed {{ background: rgba(255,255,255,0.18); }}
    QFileDialog QHeaderView::section {{
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.10);
        padding: 4px 6px;
    }}
    QFileDialog QTreeView, QFileDialog QListView {{
        background: palette(base);
        alternate-background-color: rgba(255,255,255,0.04);
        gridline-color: rgba(255,255,255,0.10);
        selection-background-color: palette(highlight);
        selection-color: palette(highlighted-text);
    }}
    """

# ──────────────────────────────
# 프레임리스 파일 대화상자 (제목바/틀까지 테마 적용)
class _FramelessFileDialog(QFileDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 네이티브 끔 + 프레임리스
        self.setOption(QFileDialog.DontUseNativeDialog, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)

        # 최소 크기(감각 유지)
        self.resize(1040, 680)

        # 상단 커스텀 제목바
        self._drag_pos: Optional[QPoint] = None
        self._build_titlebar()

        # 라운드 + 테두리
        self.setStyleSheet((self.styleSheet() or "") + """
        QFileDialog {
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 12px;
        }
        """)

    # 제목바 구성
    def _build_titlebar(self):
        lay = self.layout()  # QFileDialog 기본은 QGridLayout

        titlebar = QWidget(self)
        titlebar.setObjectName("fd_titlebar")
        hl = QHBoxLayout(titlebar)
        hl.setContentsMargins(10, 10, 10, 6)
        hl.setSpacing(8)

        lbl = QLabel(self.windowTitle() or "파일")
        try:
            f = lbl.font(); f.setPointSize(f.pointSize() + 1); lbl.setFont(f)
        except Exception:
            pass

        # 좌측: 드래그 영역 넓게
        spacer = QWidget(); spacer.setObjectName("fd_drag_area"); spacer.setMinimumWidth(10)

        # 오른쪽 컨트롤 버튼들
        btn_min = QToolButton(self); btn_min.setText("—")
        btn_max = QToolButton(self); btn_max.setText("❐")
        btn_close = QToolButton(self); btn_close.setText("✕")

        for b in (btn_min, btn_max, btn_close):
            b.setFixedSize(32, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QToolButton {
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.14);
                    border-radius: 6px;
                }
                QToolButton:hover { background: rgba(255,255,255,0.12); }
            """)

        btn_min.clicked.connect(self.showMinimized)
        def _toggle():
            self.setWindowState(Qt.WindowNoState if self.isMaximized() else Qt.WindowMaximized)
        btn_max.clicked.connect(_toggle)
        btn_close.clicked.connect(self.reject)

        hl.addWidget(lbl, 0, Qt.AlignVCenter)
        hl.addWidget(spacer, 1)
        hl.addWidget(btn_min)
        hl.addWidget(btn_max)
        hl.addWidget(btn_close)

        # ★ 핵심 수정: QGridLayout에는 insertWidget이 없다.
        #    → QGridLayout이면 setMenuBar(titlebar)로 상단에 얹는다.
        #    → QBoxLayout이면 기존처럼 맨 위에 삽입.
        if isinstance(lay, QGridLayout):
            lay.setMenuBar(titlebar)
        elif isinstance(lay, QBoxLayout):
            lay.insertWidget(0, titlebar)
        else:
            # 예외 레이아웃: 안전 폴백 — 그냥 위에 추가 시도
            try:
                # addWidget(row, col, rowSpan, colSpan)가 있을 수 있음
                if hasattr(lay, "addWidget"):
                    lay.addWidget(titlebar, 0, 0, 1, 1)  # 상단에 추가(필요 시 Qt가 재배치)
            except Exception:
                pass

        # 드래그 이동(제목바에서만)
        titlebar.installEventFilter(self)
        spacer.installEventFilter(self)
        lbl.installEventFilter(self)

    # 창 드래그 처리(제목바/드래그영역/라벨)
    def eventFilter(self, obj, ev):
        if obj.objectName() in ("fd_titlebar", "fd_drag_area") or isinstance(obj, QLabel):
            t = ev.type()
            if t == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                self._drag_pos = ev.globalPosition().toPoint() if hasattr(ev, "globalPosition") else ev.globalPos()
                return True
            if t == QEvent.MouseMove and self._drag_pos is not None and (ev.buttons() & Qt.LeftButton):
                now = ev.globalPosition().toPoint() if hasattr(ev, "globalPosition") else ev.globalPos()
                delta = now - self._drag_pos
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self._drag_pos = now
                return True
            if t in (QEvent.MouseButtonRelease, QEvent.Leave):
                self._drag_pos = None
                return False
        return super().eventFilter(obj, ev)


# ──────────────────────────────
# 정적 함수 래핑: 항상 프레임리스 커스텀 다이얼로그로
def _run_dialog(kind: str, parent, title: str, start: str, filters: str, selected: str) -> Tuple[str, str]:
    dlg = _FramelessFileDialog(parent, title, start)
    dlg.setNameFilter(filters or "All Files (*.*)")
    if selected:
        dlg.selectNameFilter(selected)

    if kind == "save":
        dlg.setAcceptMode(QFileDialog.AcceptSave)
    elif kind == "open_many":
        dlg.setFileMode(QFileDialog.ExistingFiles)
        dlg.setAcceptMode(QFileDialog.AcceptOpen)
    elif kind == "dir":
        dlg.setFileMode(QFileDialog.Directory)
        dlg.setOption(QFileDialog.ShowDirsOnly, True)
        dlg.setAcceptMode(QFileDialog.AcceptOpen)
    else:
        dlg.setAcceptMode(QFileDialog.AcceptOpen)

    # 전용 QSS(앱 전역 QSS 뒤에 덧대기)
    try:
        app = QApplication.instance()
        if app:
            app.setStyleSheet((app.styleSheet() or "") + "\n" + _file_dialog_qss())
    except Exception:
        pass

    if dlg.exec():
        if kind == "open_many":
            files = dlg.selectedFiles()
            return (";;".join(files), dlg.selectedNameFilter())
        else:
            f = dlg.selectedFiles()
            return (f[0] if f else "", dlg.selectedNameFilter())
    return ("", "")

# 원본 함수 보관
_ORIG_GET_OPEN       = QFileDialog.getOpenFileName
_ORIG_GET_OPENS      = QFileDialog.getOpenFileNames
_ORIG_GET_SAVE       = QFileDialog.getSaveFileName
_ORIG_GET_DIR        = QFileDialog.getExistingDirectory

def enable_file_dialog_fix(use_custom_frameless: bool = True) -> None:
    """
    호출하면 이후의 파일대화상자는 모두 프레임리스 커스텀으로 뜬다(제목바/틀까지 테마 적용).
    use_custom_frameless=False로 부르면 원복(네이티브/기본 제목바).
    """
    if not use_custom_frameless:
        # 원복
        QFileDialog.getOpenFileName      = staticmethod(_ORIG_GET_OPEN)   # type: ignore[assignment]
        QFileDialog.getOpenFileNames     = staticmethod(_ORIG_GET_OPENS)  # type: ignore[assignment]
        QFileDialog.getSaveFileName      = staticmethod(_ORIG_GET_SAVE)   # type: ignore[assignment]
        QFileDialog.getExistingDirectory = staticmethod(_ORIG_GET_DIR)    # type: ignore[assignment]
        return

    def _wrap_open(parent, title, start_dir, filters="All Files (*.*)", selected_filter="", options=None):
        return _run_dialog("open", parent, title, start_dir, filters, selected_filter)

    def _wrap_opens(parent, title, start_dir, filters="All Files (*.*)", selected_filter="", options=None):
        s, nf = _run_dialog("open_many", parent, title, start_dir, filters, selected_filter)
        return (s.split(";;") if s else [], nf)

    def _wrap_save(parent, title, default_path, filters="All Files (*.*)", selected_filter="", options=None):
        return _run_dialog("save", parent, title, default_path, filters, selected_filter)

    def _wrap_dir(parent, title, start_dir, options=None):
        p, _ = _run_dialog("dir", parent, title, start_dir, "All Files (*.*)", "")
        return p

    QFileDialog.getOpenFileName      = staticmethod(_wrap_open)   # type: ignore[assignment]
    QFileDialog.getOpenFileNames     = staticmethod(_wrap_opens)  # type: ignore[assignment]
    QFileDialog.getSaveFileName      = staticmethod(_wrap_save)   # type: ignore[assignment]
    QFileDialog.getExistingDirectory = staticmethod(_wrap_dir)    # type: ignore[assignment]
