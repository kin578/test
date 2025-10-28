from __future__ import annotations
from typing import List, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
    QTableWidget, QTableWidgetItem, QComboBox, QGroupBox, QFormLayout, QInputDialog, QWidget, QSizePolicy
)

import user_session
from services import auth_service

try:
    from services.audit_log import log_event
except Exception:
    def log_event(*args, **kwargs): pass


class UserAdminDialog(QDialog):
    """
    DB 기반 사용자 관리
      - 관리자: 추가/역할변경/비번변경/정지·복구/삭제
      - 일반: 내 비번 변경
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("사용자 관리")
        self.resize(720, 500)

        cu = user_session.get_current_user()
        self.me = cu.name if cu else ""
        self.my_role = auth_service.get_role(self.me)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(12)

        if self.my_role == "admin":
            # ── 상단: 사용자 추가
            add_box = QGroupBox("사용자 추가")
            form = QFormLayout(add_box)
            # 레이아웃 여백/간격 보강 (겹침 방지)
            form.setContentsMargins(12, 12, 12, 12)
            form.setHorizontalSpacing(12)
            form.setVerticalSpacing(10)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            self.ed_name = QLineEdit()
            self.ed_name.setPlaceholderText("예: hong")
            self.ed_name.setMinimumHeight(32)
            self.ed_name.setTextMargins(8, 0, 8, 0)

            self.ed_pw1  = QLineEdit()
            self.ed_pw1.setEchoMode(QLineEdit.Password)
            self.ed_pw1.setMinimumHeight(32)
            self.ed_pw1.setTextMargins(8, 0, 8, 0)

            self.ed_pw2  = QLineEdit()
            self.ed_pw2.setEchoMode(QLineEdit.Password)
            self.ed_pw2.setMinimumHeight(32)
            self.ed_pw2.setTextMargins(8, 0, 8, 0)

            self.cmb_role = QComboBox()
            self.cmb_role.addItems(["user", "admin", "viewer"])

            btn_add = QPushButton("추가")
            btn_add.setProperty("accent", True)
            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            btn_row.addWidget(btn_add)

            form.addRow("이름(ID)", self.ed_name)
            form.addRow("비밀번호", self.ed_pw1)
            form.addRow("비밀번호 확인", self.ed_pw2)
            form.addRow("역할", self.cmb_role)
            # 버튼은 별도 행으로 추가
            btn_row_host = QWidget()
            btn_row_host.setLayout(btn_row)
            form.addRow("", btn_row_host)

            lay.addWidget(add_box)
            btn_add.clicked.connect(self._on_add)

            # ── 중앙: 사용자 목록
            self.tbl = QTableWidget(0, 6)
            self.tbl.setHorizontalHeaderLabels(["이름","역할","상태","비밀번호 변경","정지/복구","삭제"])
            self.tbl.verticalHeader().setVisible(False)
            self.tbl.setAlternatingRowColors(True)
            self.tbl.horizontalHeader().setStretchLastSection(True)
            lay.addWidget(self.tbl, 1)

            self._refresh_table()
        else:
            # ── 일반 사용자: 내 비밀번호 변경
            box = QGroupBox(f"내 계정 - {self.me}")
            form = QFormLayout(box)
            # 레이아웃 여백/간격 보강 (겹침 방지 - 스크린샷 이슈 해결 포인트)
            form.setContentsMargins(16, 16, 16, 16)
            form.setHorizontalSpacing(14)
            form.setVerticalSpacing(12)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            self.my_pw1 = QLineEdit()
            self.my_pw1.setEchoMode(QLineEdit.Password)
            self.my_pw1.setMinimumHeight(34)
            self.my_pw1.setTextMargins(8, 0, 8, 0)
            self.my_pw1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self.my_pw2 = QLineEdit()
            self.my_pw2.setEchoMode(QLineEdit.Password)
            self.my_pw2.setMinimumHeight(34)
            self.my_pw2.setTextMargins(8, 0, 8, 0)
            self.my_pw2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            btn = QPushButton("비밀번호 변경")
            btn.setProperty("accent", True)
            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            btn_row.addWidget(btn)

            form.addRow("새 비밀번호", self.my_pw1)
            form.addRow("새 비밀번호 확인", self.my_pw2)
            # 버튼은 별도 행으로 추가(라벨 빈칸 유지로 겹침 방지)
            btn_row_host = QWidget()
            btn_row_host.setLayout(btn_row)
            form.addRow("", btn_row_host)

            lay.addWidget(box, 1)
            btn.clicked.connect(self._on_change_self_pw)

        # 닫기
        btn_close = QPushButton("닫기")
        rowc = QHBoxLayout()
        rowc.addStretch(1)
        rowc.addWidget(btn_close)
        lay.addLayout(rowc)
        btn_close.clicked.connect(self.accept)

    # ─────────────────────────────
    def _refresh_table(self):
        users: List[Dict[str, Any]] = auth_service.list_users()
        self.tbl.setRowCount(0)
        for u in users:
            name = u.get("name","")
            role = u.get("role","user")
            active = bool(u.get("is_active", True))

            r = self.tbl.rowCount()
            self.tbl.insertRow(r)

            self.tbl.setItem(r, 0, QTableWidgetItem(name))

            cmb = QComboBox()
            cmb.addItems(["user","admin","viewer"])
            cmb.setCurrentText(role)
            cmb.currentTextChanged.connect(lambda new_role, n=name: self._on_change_role(n, new_role))
            self.tbl.setCellWidget(r, 1, cmb)

            self.tbl.setItem(r, 2, QTableWidgetItem("사용" if active else "정지"))

            btn_pw = QPushButton("변경")
            btn_pw.clicked.connect(lambda _=None, n=name: self._on_change_pw(n))
            self.tbl.setCellWidget(r, 3, btn_pw)

            btn_toggle = QPushButton("정지" if active else "복구")
            btn_toggle.clicked.connect(lambda _=None, n=name, a=active: self._on_toggle_active(n, a))
            self.tbl.setCellWidget(r, 4, btn_toggle)

            btn_del = QPushButton("삭제")
            btn_del.setProperty("destructive", True)
            btn_del.clicked.connect(lambda _=None, n=name: self._on_delete(n))
            if name == self.me:
                btn_del.setEnabled(False)
            self.tbl.setCellWidget(r, 5, btn_del)

    def _on_add(self):
        name = (self.ed_name.text() or "").strip()
        pw1  = self.ed_pw1.text() or ""
        pw2  = self.ed_pw2.text() or ""
        role = (self.cmb_role.currentText() or "user").strip()
        if not name or not pw1:
            QMessageBox.warning(self, "확인", "이름/비밀번호를 입력해 주세요."); return
        if pw1 != pw2:
            QMessageBox.warning(self, "확인", "비밀번호가 일치하지 않습니다."); return
        try:
            auth_service.create_user(name, pw1, role=role)
            log_event("user.add", f"{name} ({role})", user=self.me)
            self.ed_name.clear(); self.ed_pw1.clear(); self.ed_pw2.clear()
            self._refresh_table()
            QMessageBox.information(self, "완료", "사용자를 추가했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_change_pw(self, name: str):
        new, ok = QInputDialog.getText(self, "비밀번호 변경", f"[{name}] 새 비밀번호:", QLineEdit.Password)
        if not ok or not new:
            return
        try:
            auth_service.change_password(name, new)
            log_event("user.pw_change", name, user=self.me)
            QMessageBox.information(self, "완료", "비밀번호를 변경했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_delete(self, name: str):
        if QMessageBox.question(self, "확인", f"[{name}] 사용자를 삭제할까요?") != QMessageBox.Yes:
            return
        try:
            auth_service.delete_user(name)
            log_event("user.delete", name, user=self.me)
            self._refresh_table()
            QMessageBox.information(self, "완료", "삭제했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _on_change_role(self, name: str, new_role: str):
        try:
            auth_service.set_role(name, new_role)
            log_event("user.role", f"{name} -> {new_role}", user=self.me)
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
            self._refresh_table()

    def _on_toggle_active(self, name: str, was_active: bool):
        try:
            auth_service.set_active(name, not was_active)
            log_event("user.active", f"{name} -> {'사용' if not was_active else '정지'}", user=self.me)
            self._refresh_table()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    # 일반 사용자
    def _on_change_self_pw(self):
        pw1 = self.my_pw1.text() or ""
        pw2 = self.my_pw2.text() or ""
        if not pw1:
            QMessageBox.warning(self, "확인", "비밀번호를 입력해 주세요."); return
        if pw1 != pw2:
            QMessageBox.warning(self, "확인", "비밀번호가 일치하지 않습니다."); return
        try:
            auth_service.change_password(self.me, pw1)
            log_event("user.pw_change", self.me, user=self.me)
            self.my_pw1.clear(); self.my_pw2.clear()
            QMessageBox.information(self, "완료", "비밀번호를 변경했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
