from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QSpinBox,
    QHBoxLayout, QPushButton, QCheckBox, QMessageBox
)
from sqlalchemy import select
from db import session_scope
from models import Equipment
from services.exporter import export_history_card_xlsx

class HistoryCardEditor(QDialog):
    """
    내보내기 전에 일부 필드/옵션을 수정하고 바로 Excel 생성
    - 특이사항, 용도, Tel 라벨, 기기번호 채우기 여부, 최근 이력 개수
    (주의) 현재 코드는 필드 편집 UI는 표시만 하며, DB는 수정하지 않습니다.
    """
    def __init__(self, equipment_code: str, parent=None):
        super().__init__(parent)
        self.code = equipment_code
        self.setWindowTitle(f"이력카드 수정/내보내기 - {equipment_code}")
        self.resize(520, 320)

        with session_scope() as s:
            self.e: Equipment = s.execute(
                select(Equipment).where(Equipment.code == equipment_code)
            ).scalars().first()

        g = QGridLayout()
        row = 0

        self.ed_name = QLineEdit(self.e.name or "")
        self.ed_model = QLineEdit(self.e.model or "")
        self.ed_size = QLineEdit(self.e.size_mm or "")
        self.ed_voltage = QLineEdit(self.e.voltage or "")
        self.ed_power = QLineEdit("" if self.e.power_kwh is None else str(self.e.power_kwh))
        self.ed_maker = QLineEdit(self.e.maker or "")
        self.ed_tel = QLineEdit(self.e.maker_phone or "")
        self.ed_location = QLineEdit(self.e.location or "")
        self.ed_use = QLineEdit(getattr(self.e, "purpose", "") or "")   # ← 용도=purpose로 수정
        self.ed_note = QLineEdit(self.e.note or "")

        for label, w in [
            ("설비명", self.ed_name), ("모델명", self.ed_model), ("설비크기", self.ed_size),
            ("전압", self.ed_voltage), ("전력(kW)", self.ed_power), ("제조회사", self.ed_maker),
            ("Tel", self.ed_tel), ("설치장소", self.ed_location), ("용도", self.ed_use), ("특이사항", self.ed_note)
        ]:
            g.addWidget(QLabel(label), row, 0)
            g.addWidget(w, row, 1)
            row += 1

        self.cb_fill_no = QCheckBox("기기번호(I17)에 관리번호를 채움")
        self.cb_fill_no.setChecked(False)
        g.addWidget(self.cb_fill_no, row, 0, 1, 2); row += 1

        self.spn_rep = QSpinBox(); self.spn_rep.setRange(1, 20); self.spn_rep.setValue(7)
        g.addWidget(QLabel("최근 이력 개수"), row, 0)
        g.addWidget(self.spn_rep, row, 1); row += 1

        btn_export = QPushButton("엑셀 내보내기")
        btn_cancel = QPushButton("닫기")
        btn_export.clicked.connect(self.on_export)
        btn_cancel.clicked.connect(self.reject)

        h = QHBoxLayout(); h.addStretch(); h.addWidget(btn_export); h.addWidget(btn_cancel)

        lay = QVBoxLayout(self)
        lay.addLayout(g)
        lay.addLayout(h)

    def on_export(self):
        try:
            # 현재 구현은 DB 수정 없이 템플릿 생성 옵션만 전달
            path = export_history_card_xlsx(
                equipment_code=self.code,
                max_repairs=self.spn_rep.value(),
                fill_machine_no=self.cb_fill_no.isChecked(),
            )
            QMessageBox.information(self, "완료", f"저장됨:\n{path}")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "실패", str(e))
