from __future__ import annotations
import os
from typing import Optional
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel, QComboBox,
    QDateEdit, QPushButton, QMessageBox, QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, QDate

from services.exporter import (
    export_repairs_xlsx, export_equipment_xlsx,
    export_consumables_xlsx, save_consumable_template_xlsx
)
# ⬇️ 이력카드 내보내기는 전용 모듈에서 직접 사용 (단일/다중)
from services.export_history_card import (
    export_history_card_xlsx, export_history_cards_multi_xlsx
)
from services.equipment_service import list_equipment
from services.export_consumable_txn import export_consumable_txn_xlsx

# 저장 경로
from settings import get_start_dir, update_last_save_dir
from ui.dialog_utils import get_save_path   # ★ 여기!

def _start_file(suggest_name: str) -> str:
    return os.path.join(get_start_dir(), suggest_name)

class ExportTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)

        # ── 설비관리대장
        grp1 = QFormLayout()
        self.ed_eq_keyword = QLineEdit()
        self.ed_eq_keyword.setPlaceholderText("설비 검색어(비우면 전체)")
        btn_eq = QPushButton("설비관리대장 내보내기 (엑셀)")
        grp1.addRow("설비 검색", self.ed_eq_keyword)
        grp1.addRow(btn_eq)

        # ── 개선·수리
        grp2 = QFormLayout()
        self.cmb_equipment = QComboBox(); self._refresh_equipment_list()
        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True)
        self.chk_rep_range = QCheckBox("기간 필터 사용")
        btn_rep = QPushButton("개선·수리 내보내기 (엑셀)")
        grp2.addRow("설비 선택(전체=비움)", self.cmb_equipment)
        grp2.addRow(self.chk_rep_range)
        grp2.addRow("시작일", self.date_from)
        grp2.addRow("종료일", self.date_to)
        grp2.addRow(btn_rep)

        # ── 이력카드(단일/전체)
        grp3 = QFormLayout()
        self.cmb_equipment_card = QComboBox(); self._refresh_equipment_list(self.cmb_equipment_card)  # (전체) 포함
        btn_card = QPushButton("이력카드(엑셀) 내보내기")
        grp3.addRow("설비 선택 (전체 포함)", self.cmb_equipment_card)
        grp3.addRow(btn_card)

        # ── 소모품 입출고
        grp4 = QFormLayout()
        self.txn_from = QDateEdit(); self.txn_from.setCalendarPopup(True)
        self.txn_to = QDateEdit(); self.txn_to.setCalendarPopup(True)
        self.chk_txn_range = QCheckBox("기간 필터 사용")
        btn_txn = QPushButton("소모품 입출고 이력 내보내기 (엑셀)")
        row_x = QHBoxLayout()
        btn_list = QPushButton("소모품 목록 내보내기")
        btn_tpl = QPushButton("소모품 양식 저장")
        row_x.addWidget(btn_list); row_x.addWidget(btn_tpl); row_x.addStretch(1)
        grp4.addRow(self.chk_txn_range)
        grp4.addRow("시작일", self.txn_from)
        grp4.addRow("종료일", self.txn_to)
        grp4.addRow(btn_txn)
        grp4.addRow(row_x)

        root.addLayout(grp1); root.addSpacing(8)
        root.addLayout(grp2); root.addSpacing(8)
        root.addLayout(grp3); root.addSpacing(8)
        root.addLayout(grp4); root.addStretch(1)

        # 연결
        btn_eq.clicked.connect(self._do_export_equipment)
        btn_rep.clicked.connect(self._do_export_repairs)
        btn_card.clicked.connect(self._do_export_card)
        btn_txn.clicked.connect(self._do_export_txn)
        btn_list.clicked.connect(self._do_export_cons_list)
        btn_tpl.clicked.connect(self._do_save_cons_tpl)

        # 날짜 기본값(표시용)
        today = QDate.currentDate()
        self.date_from.setDate(today.addMonths(-1))
        self.date_to.setDate(today)
        self.txn_from.setDate(today.addMonths(-1))
        self.txn_to.setDate(today)

    # ─────────────────────────────────────────────────────────
    def _refresh_equipment_list(self, target: Optional[QComboBox] = None):
        cb = target or self.cmb_equipment
        cb.clear(); cb.addItem("(전체)", 0)  # 콤보의 0번은 전체
        for e in list_equipment(""):
            cb.addItem(f"{e.code} - {e.name}", e.id)

    def _get_date(self, de: QDateEdit) -> Optional[date]:
        try: return de.date().toPython()
        except Exception: return None

    # ─────────────────────────────────────────────────────────
    def _do_export_equipment(self):
        kw = self.ed_eq_keyword.text().strip()
        path = get_save_path(self, "설비관리대장 내보내기",
                             _start_file("설비관리대장_내보내기.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_equipment_xlsx(keyword=kw, path=path)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _do_export_repairs(self):
        eid = self.cmb_equipment.currentData() or None
        d1 = self._get_date(self.date_from) if self.chk_rep_range.isChecked() else None
        d2 = self._get_date(self.date_to) if self.chk_rep_range.isChecked() else None
        path = get_save_path(self, "개선·수리 내보내기",
                             _start_file("개선수리_내보내기.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_repairs_xlsx(path=path, equipment_id=eid, date_from=d1, date_to=d2, columns=None)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _do_export_card(self):
        idx = self.cmb_equipment_card.currentIndex()
        if idx <= 0:
            codes = [e.code for e in list_equipment("") if getattr(e, "code", None)]
            if not codes:
                QMessageBox.information(self, "안내", "내보낼 설비가 없습니다."); return
            default_name = f"이력카드_묶음_{len(codes)}대.xlsx"
            path = get_save_path(self, "이력카드 묶음으로 저장",
                                 _start_file(default_name), "Excel Files (*.xlsx)")
            if not path: return
            try:
                out = export_history_cards_multi_xlsx(codes, path=path)
                update_last_save_dir(os.path.dirname(out))
                QMessageBox.information(self, "완료", f"저장됨:\n{out}")
            except Exception as e:
                QMessageBox.critical(self, "에러", str(e))
            return

        code = (self.cmb_equipment_card.currentText().split(" - ", 1)[0]).strip()
        path = get_save_path(self, "이력카드 저장",
                             _start_file(f"{code}_이력카드.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_history_card_xlsx(equipment_code=code, path=path, template_path=None, logo_path=None)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _do_export_txn(self):
        d1 = self._get_date(self.txn_from) if self.chk_txn_range.isChecked() else None
        d2 = self._get_date(self.txn_to) if self.chk_txn_range.isChecked() else None
        path = get_save_path(self, "소모품 입출고 이력 내보내기",
                             _start_file("소모품_입출고이력.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_consumable_txn_xlsx(keyword="", start_date=d1, end_date=d2, path=path)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _do_export_cons_list(self):
        path = get_save_path(self, "소모품 목록 내보내기",
                             _start_file("소모품_목록.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_consumables_xlsx(path=path)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _do_save_cons_tpl(self):
        path = get_save_path(self, "소모품 양식 저장",
                             _start_file("소모품_양식.xlsx"), "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = save_consumable_template_xlsx(path=path)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
