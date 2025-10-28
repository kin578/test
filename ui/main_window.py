from __future__ import annotations
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QMessageBox, QApplication,
    QVBoxLayout, QHBoxLayout, QMenuBar, QStatusBar, QToolButton
)
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QMouseEvent
from PySide6.QtCore import Qt, QFile, QPoint, QRect, QEvent
from PySide6.QtWidgets import QGraphicsDropShadowEffect

# ─────────────────────────────────────────────────────────
# 테마 모듈 가져오기 (우리 프로젝트 전용 theme.py 우선, 없으면 기존 벤더 모듈 폴백)
# - set_theme(app): py_dracula_dark.qss 적용
# - apply_overlay(app): 오버레이가 있으면 얹음(없으면 조용히 무시)
try:
    from theme import set_theme, apply_overlay            # 우리 프로젝트에서 제공(추천)
except Exception:
    try:
        from pydracula_theme import set_theme             # 벤더 폴백 1
    except Exception:
        def set_theme(app, *args, **kwargs):              # 최후 폴백(없어도 앱은 뜸)
            return
    try:
        from pydracula_overlay import apply_overlay       # 벤더 폴백 2
    except Exception:
        def apply_overlay(app, *args, **kwargs):
            return

"""
주의: no_white_theme(강한 다크 팔레트)는 여기서 사용하지 않는다.
필요 시 app.py에서만 선택적으로 켜고, 이 파일은 '순정 Dracula QSS'만 신경 씀.
"""

# ===== 상단 버튼/레이아웃 사이즈 튜닝 상수 =====
CTRL_BTN_SIZE = 36
CTRL_BTN_RADIUS = 12
CTRL_BTN_FONT_PX = 18
HEADER_BOTTOM_GAP = 8
# =====================================================

# 레이지 탭
from ui.lazy_tabs import LazyTabWidget

# 서비스
from services.backup_service import backup_wizard, restore_wizard
from db import ensure_db


# ─────────────────────────────────────────────────────────
def bootstrap():
    """
    DB 스키마 보장 등 초기 작업.
    이 함수는 '앱 전체에서 1번만' 실행되면 충분해서,
    아래 MainWindow.__init__에서 중복을 방지하는 가드를 둔다.
    """
    ensure_db()


def _patch_combobox_arrow(app: QApplication):
    """
    QComboBox의 ▼ 화살표 이미지를 QRC(:/...) → 로컬 파일 경로 순서로 찾아서 스타일시트에 주입.
    (아이콘이 없어도 앱은 정상 동작하므로 실패해도 조용히 스킵)
    """
    qrc_candidates = [
        ":/icons/images/icons/cil-arrow-bottom-2.png",
        ":/icons/images/icons/cil-arrow-bottom.png",
        ":/images/icons/cil-arrow-bottom-2.png",
        ":/images/icons/cil-arrow-bottom.png",
    ]
    fs_candidates = [
        "images/icons/cil-arrow-bottom-2.png",
        "images/icons/cil-arrow-bottom.png",
        "icons/images/icons/cil-arrow-bottom-2.png",
        "icons/images/icons/cil-arrow-bottom.png",
        "vendor/pydracula/images/icons/cil-arrow-bottom-2.png",
        "vendor/pydracula/images/icons/cil-arrow-bottom.png",
    ]
    url = None
    # 1) QRC 우선
    for c in qrc_candidates:
        try:
            if QFile.exists(c):
                url = c
                break
        except Exception:
            pass
    # 2) 로컬 폴백
    if url is None:
        for p in fs_candidates:
            if Path(p).exists():
                url = p
                break
    if url is None:
        return  # 아이콘 파일이 없어도 앱은 계속

    # 전역 QSS 뒤에 살짝 덮어쓰기(다른 위젯 영향 최소화)
    try:
        app.setStyleSheet((app.styleSheet() or "") + f"""
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
        """)
    except Exception:
        pass


def _ensure_theme_applied_once():
    """
    테마/오버레이를 '메인 윈도우가 뜰 때' 다시 보강 적용.
    - app.py에서 이미 set_theme을 호출했더라도, 환경에 따라 누락되는 사례가 있어
      여기서 한 번 더 보장한다.
    - 단, QApplication 전역 속성(app.setProperty)을 사용해 '중복 재적용'은 막는다.
    """
    app = QApplication.instance()
    if app is None:
        return
    if getattr(app, "property", lambda x: None)("theme_applied"):
        # 이미 다른 곳(app.py 등)에서 적용됨
        return
    try:
        set_theme(app, "dark")         # py_dracula_dark.qss
        apply_overlay(app)             # 오버레이가 있으면 얹음
        _patch_combobox_arrow(app)     # ▼ 아이콘 보정
        app.setProperty("theme_applied", True)
    except Exception:
        # 테마 실패해도 앱은 계속
        pass


def _ensure_bootstrap_once():
    """
    DB 초기화 등 bootstrap을 '앱 전체에서 1회'만 실행.
    app.py와 여기서 둘 다 호출되더라도, 전역 속성으로 중복을 막는다.
    """
    app = QApplication.instance()
    if app is None:
        # 이론상 여기 올 일은 거의 없음(항상 QApplication 이후 호출)
        bootstrap()
        return
    if not getattr(app, "property", lambda x: None)("bootstrap_done"):
        try:
            bootstrap()
        finally:
            try:
                app.setProperty("bootstrap_done", True)
            except Exception:
                pass


class MainWindow(QMainWindow):
    """프레임리스 카드형 메인 창 (겉은 투명, 안쪽 카드만 보임)"""
    RESIZE_MARGIN = 6  # 가장자리 리사이즈 감지 폭(px)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("설비 관리 프로그램")

        # ── 1) 부트스트랩(중복 호출 방지)
        _ensure_bootstrap_once()

        # ── 2) 테마 재보장(중복 적용 방지)
        _ensure_theme_applied_once()

        # ── 3) 창 프레임/배경 설정
        #     - OS 기본 프레임을 숨기고(Frameless), 배경을 투명으로 둬서
        #       '카드(card) 위젯'만 동글동글하게 보이도록 함.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # ── 루트 / 카드 컨테이너 구성
        self._root = QWidget(self)
        self._root.setObjectName("root")
        self._root_lay = QVBoxLayout(self._root)
        self._root_lay.setContentsMargins(16, 16, 16, 16)  # 복원 상태 여백
        self._root_lay.setSpacing(0)

        self.card = QWidget(self._root)
        self.card.setObjectName("card")
        self._card_lay = QVBoxLayout(self.card)
        self._card_lay.setContentsMargins(14, 14, 14, 14)
        self._card_lay.setSpacing(8)

        # ── 그림자(카드 아래쪽 부드러운 그림자)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 10)
        self._shadow.setColor(Qt.black)
        self.card.setGraphicsEffect(self._shadow)

        # ── 상단바 (메뉴 + 창 제어 버튼)
        header = QWidget(self.card)
        header.setObjectName("header")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, HEADER_BOTTOM_GAP)
        header_lay.setSpacing(10)

        self.menubar = QMenuBar(self.card)
        self.menubar.setObjectName("menubar")
        header_lay.addWidget(self.menubar, 1)

        self.btn_min = QToolButton(self.card);  self.btn_min.setObjectName("btnMin")
        self.btn_max = QToolButton(self.card);  self.btn_max.setObjectName("btnMax")
        self.btn_close = QToolButton(self.card);self.btn_close.setObjectName("btnClose")
        self.btn_min.setText("—"); self.btn_min.setToolTip("최소화")
        self.btn_max.setText("□"); self.btn_max.setToolTip("최대화/복원")
        self.btn_close.setText("✕"); self.btn_close.setToolTip("닫기")

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(CTRL_BTN_SIZE, CTRL_BTN_SIZE)

        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max_restore)
        self.btn_close.clicked.connect(self.close)

        header_lay.addWidget(self.btn_min, 0, Qt.AlignRight)
        header_lay.addWidget(self.btn_max, 0, Qt.AlignRight)
        header_lay.addWidget(self.btn_close, 0, Qt.AlignRight)

        self._card_lay.addWidget(header)

        # ── 탭 (레이지 로딩: 클릭할 때 생성)
        self.tabs = LazyTabWidget(self.card)
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setElideMode(Qt.ElideRight)

        # 탭 팩토리(처음 열릴 때만 생성)
        self.tab_equipment = None
        self.tab_history   = None
        self.tab_repair    = None
        self.tab_cons      = None
        self.tab_export    = None

        def _mk_equipment():
            from ui.tabs.equipment_tab import EquipmentTab
            self.tab_equipment = EquipmentTab(
                on_open_history=self.open_history_by_code,
                on_search_done=None,
                on_edited=None
            )
            self.tab_equipment.setWindowTitle("설비관리대장")
            return self.tab_equipment

        def _mk_history():
            from ui.tabs.history_tab import HistoryTab
            self.tab_history = HistoryTab(on_open_repair=self._open_repair_from_history)
            self.tab_history.setWindowTitle("이력카드")
            return self.tab_history

        def _mk_repair():
            from ui.tabs.repair_tab import RepairTab
            self.tab_repair = RepairTab(on_saved_open_history=self.open_history_by_code)
            self.tab_repair.setWindowTitle("개선·수리")
            return self.tab_repair

        def _mk_cons():
            from ui.tabs.consumable_tab import ConsumableTab
            self.tab_cons = ConsumableTab()
            self.tab_cons.setWindowTitle("소모품")
            return self.tab_cons

        def _mk_export():
            from ui.tabs.export_tab import ExportTab
            self.tab_export = ExportTab()
            self.tab_export.setWindowTitle("내보내기")
            return self.tab_export

        self.idx_equipment = self.tabs.addLazyTab(_mk_equipment, "설비관리대장")
        self.idx_history   = self.tabs.addLazyTab(_mk_history,   "이력카드")
        self.idx_repair    = self.tabs.addLazyTab(_mk_repair,    "개선·수리")
        self.idx_cons      = self.tabs.addLazyTab(_mk_cons,      "소모품")
        self.idx_export    = self.tabs.addLazyTab(_mk_export,    "내보내기")

        # 시작 탭을 즉시 만들어 첫 화면을 빈칸 없이
        self.tabs.setCurrentIndex(self.idx_equipment)
        self.tabs.build_now(self.idx_equipment)

        self._card_lay.addWidget(self.tabs, 1)

        # 상태바
        self._status = QStatusBar(self.card)
        self._status.setObjectName("status")
        self._card_lay.addWidget(self._status)

        self._root_lay.addWidget(self.card, 1)
        self.setCentralWidget(self._root)

        # 메뉴 구성
        self._build_menu(self.menubar)
        QShortcut(QKeySequence("Ctrl+Alt+U"), self, activated=self.open_user_admin)

        # 마우스 트래킹(프레임리스 드래그/리사이즈에 필요)
        for w in (self, self._root, self.card, self.menubar, self.tabs):
            w.setMouseTracking(True)

        # 리사이즈 상태값
        self._resize_active = False
        self._resize_edges: set[str] = set()
        self._resize_origin_geom: QRect | None = None
        self._resize_origin_mouse: QPoint | None = None

        # 드래그/더블클릭 핸들러
        header.installEventFilter(self)
        self.menubar.installEventFilter(self)
        # 탭바에서도 더블클릭으로 최대화/복원
        self.tabs.tabBar().installEventFilter(self)

        # 드래그 제스처 상태 (더블클릭과 충돌 방지)
        self._drag_arm = False     # 클릭 후, 아직 움직이지 않은 상태
        self._os_dragging = False  # OS 드래그 시작 여부

        # 최종 스타일 적용(카드 모양/여백)
        self._apply_clean_style()
        self._apply_maximized_insets(self.isMaximized())

    # ──────────────────────────────────────────────
    def _apply_clean_style(self):
        """
        메인 '카드'를 배경에서 떠 있는 패널처럼 보이게 하는 QSS.
        Dracula QSS의 색상 팔레트(palette(base) 등)에 맞춰 최대한 얕게 덮어쓴다.
        """
        self.setStyleSheet(f"""
        QMainWindow {{ background: transparent; }}
        QWidget#root {{ background: transparent; }}
        /* 카드(프레임) 배경을 컨텐츠(base)와 동일 톤으로 */
        QWidget#card {{
            background: palette(base);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
        }}
        QWidget#header {{ background: transparent; }}
        QMenuBar#menubar {{ background: transparent; border: none; padding: 0px; }}
        QMenuBar#menubar::item {{ padding: 6px 10px; margin: 4px 6px; border-radius: 8px; }}
        QMenuBar#menubar::item:selected {{ background: rgba(255,255,255,0.06); }}

        QToolButton#btnMin, QToolButton#btnMax, QToolButton#btnClose {{
            min-width: {CTRL_BTN_SIZE}px;  max-width: {CTRL_BTN_SIZE}px;
            min-height: {CTRL_BTN_SIZE}px; max-height: {CTRL_BTN_SIZE}px;
            font-size: {CTRL_BTN_FONT_PX}px;
            border: 1px solid rgba(255,255,255,0.18);
            background: rgba(255,255,255,0.05);
            color: palette(button-text);
            border-radius: {CTRL_BTN_RADIUS}px;
        }}
        QToolButton#btnMin:hover, QToolButton#btnMax:hover {{ background: rgba(255,255,255,0.12); }}
        QToolButton#btnClose:hover {{ background: rgba(255,80,80,0.28); }}

        QTabBar::tab {{ padding: 7px 12px; margin: 6px 6px 0 0; border-radius: 10px; background: rgba(255,255,255,0.04); }}
        QTabBar::tab:selected {{ background: rgba(255,255,255,0.10); }}
        QTabWidget::pane {{ border: none; top: 6px; }}
        QStatusBar#status {{ background: transparent; border-top: 1px solid rgba(255,255,255,0.06); padding: 6px 4px; }}
        """)

    # ──────────────────────────────────────────────
    def _apply_maximized_insets(self, is_max: bool):
        """
        최대화 상태에서는 카드의 '모서리 둥글게'와 '그림자'를 꺼서
        화면 전체에 꽉 차게 보이도록 하고, 복원 시 다시 되돌린다.
        """
        if is_max:
            self._root_lay.setContentsMargins(0, 0, 0, 0)
            if "border-radius: 16px;" in self.card.styleSheet():
                self.card.setStyleSheet(self.card.styleSheet().replace("border-radius: 16px;", "border-radius: 0px;"))
            if self._shadow:
                self._shadow.setEnabled(False)
            self.btn_max.setText("❐")
        else:
            self._root_lay.setContentsMargins(16, 16, 16, 16)
            if "border-radius: 0px;" in self.card.styleSheet():
                self.card.setStyleSheet(self.card.styleSheet().replace("border-radius: 0px;", "border-radius: 16px;"))
            if self._shadow:
                self._shadow.setEnabled(True)
            self.btn_max.setText("□")

    def changeEvent(self, ev):
        """윈도우 상태(최대화/복원) 변경 시 여백/그림자 갱신"""
        if ev.type() == QEvent.WindowStateChange:
            self._apply_maximized_insets(self.isMaximized())
        super().changeEvent(ev)

    # ──────────────────────────────────────────────
    # 프레임리스: 헤더/메뉴바/탭바 더블클릭(토글) + 드래그(빈공간에서만) + 가장자리 리사이즈
    def eventFilter(self, obj, ev):
        if obj.objectName() in ("header",) or obj is self.menubar or obj is self.tabs.tabBar():
            typ = ev.type()

            if typ == QEvent.MouseButtonDblClick:
                # 탭바/메뉴바/헤더 어디서든 더블클릭 → 최대화/복원
                self._toggle_max_restore()
                return True

            if typ == QEvent.MouseButtonPress:
                mev: QMouseEvent = ev  # type: ignore
                if mev.button() == Qt.LeftButton:
                    if obj is self.menubar:
                        # 메뉴 항목 위에서는 드래그 금지(클릭 동작과 충돌)
                        act = self.menubar.actionAt(mev.pos())
                        if act is not None:
                            self._drag_arm = False
                            return False
                    self._drag_arm = True     # 눌렀고 빈 영역일 가능성
                    self._os_dragging = False
                    return False

            if typ == QEvent.MouseMove:
                mev: QMouseEvent = ev  # type: ignore
                if self._drag_arm and (mev.buttons() & Qt.LeftButton):
                    if obj is self.menubar:
                        # 메뉴 항목 위를 드래그하면 바로 포기
                        act = self.menubar.actionAt(mev.pos())
                        if act is not None:
                            self._drag_arm = False
                            return False
                    if not self._os_dragging:
                        self._os_dragging = True
                        self._start_os_drag()
                        return True

            if typ in (QEvent.MouseButtonRelease, QEvent.Leave):
                self._drag_arm = False
                self._os_dragging = False
                return False

        return super().eventFilter(obj, ev)

    def _start_os_drag(self):
        """
        윈도우에서 프레임리스 윈도우를 OS가 인식하는 '제목바 드래그'처럼 이동시키기.
        (다른 OS에서는 조용히 스킵)
        """
        if sys.platform.startswith("win"):
            try:
                import ctypes
                user32 = ctypes.windll.user32
                WM_NCLBUTTONDOWN = 0x00A1
                HTCAPTION = 0x0002
                hwnd = int(self.winId())
                user32.ReleaseCapture()
                user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
                return
            except Exception:
                pass

    # ──────────────────────────────────────────────
    # 가장자리 리사이즈 구현(프레임리스라 직접 처리)
    def mouseMoveEvent(self, e: QMouseEvent):
        gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
        edges = self._hit_test_edges_global(gp)
        self._set_resize_cursor(edges)
        if self._resize_active and self._resize_origin_geom and self._resize_origin_mouse and self._resize_edges:
            self._do_resize(gp)
            return
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
            edges = self._hit_test_edges_global(gp)
            if edges:
                self._resize_active = True
                self._resize_edges = edges
                self._resize_origin_geom = self.geometry()
                self._resize_origin_mouse = gp
                return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self._resize_active:
            self._resize_active = False
            self._resize_edges.clear()
            self.unsetCursor()
            return
        super().mouseReleaseEvent(e)

    def _hit_test_edges_global(self, gp: QPoint) -> set[str]:
        """마우스가 창 경계 근처(RESIZE_MARGIN)인지 검사해서, 어느 방향인지 세트로 반환"""
        m = self.RESIZE_MARGIN
        g: QRect = self.frameGeometry()
        edges: set[str] = set()
        if g.left() <= gp.x() <= g.left() + m: edges.add("left")
        if g.right() - m <= gp.x() <= g.right(): edges.add("right")
        if g.top() <= gp.y() <= g.top() + m: edges.add("top")
        if g.bottom() - m <= gp.y() <= g.bottom(): edges.add("bottom")
        return edges

    def _set_resize_cursor(self, edges: set[str]):
        """경계 방향에 맞는 커서를 표시(사용자에게 리사이즈 가능한 곳이라는 힌트 제공)"""
        if not edges or self._resize_active:
            if not self._resize_active:
                self.unsetCursor()
            return
        if "left" in edges and "top" in edges:
            self.setCursor(Qt.SizeFDiagCursor)
        elif "right" in edges and "bottom" in edges:
            self.setCursor(Qt.SizeFDiagCursor)
        elif "right" in edges and "top" in edges:
            self.setCursor(Qt.SizeBDiagCursor)
        elif "left" in edges and "bottom" in edges:
            self.setCursor(Qt.SizeBDiagCursor)
        elif "left" in edges or "right" in edges:
            self.setCursor(Qt.SizeHorCursor)
        elif "top" in edges or "bottom" in edges:
            self.setCursor(Qt.SizeVerCursor)

    def _do_resize(self, gp_now: QPoint):
        """마우스 이동량을 계산해 새 사각형을 만들고 setGeometry로 즉시 반영"""
        g0: QRect = self._resize_origin_geom  # type: ignore
        p0: QPoint = self._resize_origin_mouse  # type: ignore
        dx = gp_now.x() - p0.x()
        dy = gp_now.y() - p0.y()
        x, y, w, h = g0.x(), g0.y(), g0.width(), g0.height()
        minw, minh = 900, 560  # 최소 크기(너가 원하던 감각 유지)
        if "left" in self._resize_edges:
            x = x + dx; w = max(minw, w - dx)
        if "right" in self._resize_edges:
            w = max(minw, w + dx)
        if "top" in self._resize_edges:
            y = y + dy; h = max(minh, h - dy)
        if "bottom" in self._resize_edges:
            h = max(minh, h + dy)
        self.setGeometry(QRect(x, y, w, h))

    def _toggle_max_restore(self):
        """제목바 버튼/더블클릭에서 호출: 최대화 <-> 복원 토글"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._apply_maximized_insets(self.isMaximized())

    # ──────────────────────────────────────────────
    def _build_menu(self, menubar: QMenuBar):
        """
        상단 메뉴 바 구성.
        - 요청대로 '테마 전환' 같은 메뉴는 생성하지 않는다(항상 고정 테마).
        """
        # 도구
        m_tools = menubar.addMenu("도구")
        act_backup = QAction("백업 생성", self)
        act_restore = QAction("복구 마법사…", self)
        act_backup.triggered.connect(self._do_backup)
        act_restore.triggered.connect(self._do_restore)
        m_tools.addAction(act_backup); m_tools.addAction(act_restore)

        # 보기(탭 위치만 바꾸는 간단 옵션)
        m_view = menubar.addMenu("보기")
        act_tab_top = QAction("탭 위쪽 배치", self, checkable=True)
        act_tab_bottom = QAction("탭 아래쪽 배치", self, checkable=True)
        act_tab_top.setChecked(True)

        def _top():
            self.tabs.setTabPosition(QTabWidget.North)
            act_tab_top.setChecked(True)
            act_tab_bottom.setChecked(False)

        def _bottom():
            self.tabs.setTabPosition(QTabWidget.South)
            act_tab_top.setChecked(False)
            act_tab_bottom.setChecked(True)

        act_tab_top.triggered.connect(_top)
        act_tab_bottom.triggered.connect(_bottom)
        m_view.addAction(act_tab_top); m_view.addAction(act_tab_bottom)

        # 관리
        m_admin = menubar.addMenu("관리")
        act_user_admin = QAction("사용자 관리… (Ctrl+Alt+U)", self)
        act_user_admin.triggered.connect(self.open_user_admin)
        m_admin.addAction(act_user_admin)

        # 단축키(중복 방지차원에서 한 번만 등록)
        QShortcut(QKeySequence("Ctrl+Alt+U"), self, activated=self.open_user_admin)

    def _do_backup(self):
        """백업 마법사 실행"""
        try:
            p = backup_wizard(self)
            self._status.showMessage(f"백업 완료: {p}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _do_restore(self):
        """복구 마법사 실행"""
        try:
            restore_wizard(self)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _ensure_history_ready(self):
        """이력카드 탭이 아직 만들어지지 않았다면 지금 생성"""
        self.tabs.build_now(self.idx_history)

    def _ensure_repair_ready(self):
        """수리 탭이 아직 만들어지지 않았다면 지금 생성"""
        self.tabs.build_now(self.idx_repair)

    def open_history_by_code(self, code: str):
        """
        외부(설비관리대장/수리 탭 등)에서 '코드로 이력카드 열기' 요청이 올 때 사용.
        - 레이지 탭이므로 먼저 해당 탭을 보장하고, 화면을 전환한다.
        """
        try:
            self._ensure_history_ready()
            if hasattr(self.tab_history, "open_by_code"):
                self.tab_history.open_by_code(code)
            else:
                # 과거 호환: 메서드명이 load_for_equipment 인 버전 지원
                self.tab_history.load_for_equipment(code)
            self.tabs.setCurrentIndex(self.idx_history)

            # 수리 탭에도 선택 장비 동기화
            self._ensure_repair_ready()
            if hasattr(self.tab_repair, "set_active_equipment_by_code"):
                self.tab_repair.set_active_equipment_by_code(code)
        except Exception as e:
            QMessageBox.critical(self, "이력카드 열기 오류", str(e))

    def _open_repair_from_history(self, repair_id: int, equipment_id: int):
        """이력카드에서 '해당 수리 기록 열기'를 눌렀을 때 수리 탭 전환"""
        try:
            self._ensure_repair_ready()
            if hasattr(self.tab_repair, "open_record"):
                self.tab_repair.open_record(repair_id, equipment_id)
            self.tabs.setCurrentIndex(self.idx_repair)
        except Exception as e:
            QMessageBox.critical(self, "수리 탭 열기 오류", str(e))

    def open_user_admin(self):
        """관리 메뉴 → 사용자 관리 대화상자"""
        try:
            from ui.dialogs.user_admin_dialog import UserAdminDialog
            dlg = UserAdminDialog(self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"사용자 관리 화면을 열 수 없습니다.\n{e}")
