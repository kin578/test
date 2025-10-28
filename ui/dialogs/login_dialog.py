from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QWidget, QCheckBox, QToolButton, QSizePolicy
)
from PySide6.QtGui import QFont, QAction, QMouseEvent
from PySide6.QtCore import Qt, QPoint

import settings
from services import auth_service
import user_session

# 감사 로그 모듈이 없을 수도 있으므로 방어
try:
    from services.audit_log import log_event
except Exception:
    def log_event(*args, **kwargs): pass


class LoginDialog(QDialog):
    """
    로그인 다이얼로그 (프레임리스 유지, 기능 동일)
    - 전역 PyDracula QSS를 그대로 따름 (커스텀 setStyleSheet 없음)
    - Enter 키는 '기본 버튼(default=True)' 한 경로로만 처리
    - 중복 실행 방지 가드(_submitting)로 오류창 두 번 뜨는 문제 해결
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # 프레임리스 유지
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setWindowTitle("로그인")
        self.setObjectName("LoginDialog")

        # 기본 관리자 보장 (없으면 admin/1234 생성)
        auth_service.ensure_default_admin()

        # 설정 로드: 이름 기억
        cfg = settings._load()
        last_name = cfg.get("last_login_name", "")
        remember = cfg.get("remember_login_name", True)

        # ───────── 레이아웃
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # 헤더
        header = QHBoxLayout()
        title = QLabel("🔧 설비 관리 프로그램")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        f = QFont(); f.setPointSize(14); f.setBold(True); title.setFont(f)

        btn_close = QToolButton(self)
        btn_close.setText("✕")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setToolTip("닫기")
        btn_close.clicked.connect(self.reject)

        header.addWidget(title, 1)
        header.addWidget(btn_close, 0, Qt.AlignTop)
        root.addLayout(header)

        subtitle = QLabel("계정으로 로그인해 주세요")
        subtitle.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root.addWidget(subtitle)

        # 이름
        row_name = QVBoxLayout()
        cap_name = QLabel("이름")
        self.ed_name = QLineEdit(self)
        self.ed_name.setPlaceholderText("예: 홍길동")
        self.ed_name.setText(last_name)
        row_name.addWidget(cap_name)
        row_name.addWidget(self.ed_name)
        root.addLayout(row_name)

        # 비밀번호 + 👁
        row_pw = QVBoxLayout()
        cap_pw = QLabel("비밀번호")
        row_pw.addWidget(cap_pw)

        pw_line = QHBoxLayout()
        self.ed_pw = QLineEdit(self)
        self.ed_pw.setPlaceholderText("비밀번호")
        self.ed_pw.setEchoMode(QLineEdit.Password)

        self.btn_eye = QToolButton(self)
        self.btn_eye.setText("👁")
        self.btn_eye.setCheckable(True)
        self.btn_eye.setToolTip("비밀번호 보기")
        self.btn_eye.setCursor(Qt.PointingHandCursor)
        self.btn_eye.clicked.connect(self._toggle_pw)

        pw_line.addWidget(self.ed_pw, 1)
        pw_line.addWidget(self.btn_eye, 0, Qt.AlignVCenter)
        row_pw.addLayout(pw_line)
        root.addLayout(row_pw)

        # 옵션
        row_opt = QHBoxLayout()
        self.cb_remember = QCheckBox("이름 기억하기")
        self.cb_remember.setChecked(bool(remember))
        row_opt.addWidget(self.cb_remember)
        row_opt.addStretch(1)
        root.addLayout(row_opt)

        # 버튼
        row_btns = QHBoxLayout()
        row_btns.addStretch(1)
        self.btn_ok = QPushButton("로그인")
        self.btn_ok.setDefault(True)  # ← Enter 키는 이 버튼 '하나'만 탄다
        self.btn_cancel = QPushButton("취소")
        row_btns.addWidget(self.btn_ok)
        row_btns.addWidget(self.btn_cancel)
        root.addLayout(row_btns)

        # 시그널 (중복 호출 경로 제거)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        # ❌ 더 이상 returnPressed를 _on_ok에 직접 연결하지 않는다.
        #    기본 버튼(default=True)이 Enter를 처리하므로 중복을 방지.
        # self.ed_name.returnPressed.connect(self._on_ok)
        # self.ed_pw.returnPressed.connect(self._on_ok)

        # 선택: Ctrl+Enter로도 로그인 (중복 아님)
        act_login = QAction(self)
        act_login.setShortcut("Ctrl+Return")
        act_login.triggered.connect(self._on_ok)
        self.addAction(act_login)

        # 드래그 이동 상태
        self._drag_active = False
        self._drag_origin_global: QPoint | None = None
        self._drag_origin_window: QPoint | None = None

        # 중복 실행 방지 플래그
        self._submitting = False

    # ───────── 프레임리스 드래그 이동
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
            self._drag_active = True
            self._drag_origin_global = gp
            self._drag_origin_window = self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_active and self._drag_origin_global and self._drag_origin_window:
            gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
            delta = gp - self._drag_origin_global
            self.move(self._drag_origin_window + delta)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._drag_active = False
        super().mouseReleaseEvent(e)

    # ───────── 동작
    def _toggle_pw(self):
        if self.btn_eye.isChecked():
            self.ed_pw.setEchoMode(QLineEdit.Normal)
            self.btn_eye.setToolTip("비밀번호 숨기기")
        else:
            self.ed_pw.setEchoMode(QLineEdit.Password)
            self.btn_eye.setToolTip("비밀번호 보기")

    def _on_ok(self):
        # 중복 진입 가드
        if self._submitting:
            return
        self._submitting = True
        try:
            name = (self.ed_name.text() or "").strip()
            pw   = self.ed_pw.text() or ""
            if not name or not pw:
                QMessageBox.warning(self, "확인", "이름과 비밀번호를 입력해 주세요.")
                return

            if not auth_service.verify(name, pw):
                QMessageBox.critical(self, "실패", "이름 또는 비밀번호가 올바르지 않습니다.")
                return

            role = auth_service.get_role(name)
            user_session.set_current_user(name, role=role)

            cfg = settings._load()
            cfg["last_login_name"] = name if self.cb_remember.isChecked() else ""
            cfg["remember_login_name"] = bool(self.cb_remember.isChecked())
            settings._save(cfg)

            log_event("login", "login success", user=name)
            self.accept()
        finally:
            self._submitting = False
