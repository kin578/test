from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                               QDialogButtonBox, QMessageBox)
from services.consumable_service import add_consumable

class NewConsumableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("소모품 신규 등록")
        form = QFormLayout(self)
        self.ed_name = QLineEdit()
        self.ed_spec = QLineEdit()
        self.sp_stock = QDoubleSpinBox(); self.sp_stock.setDecimals(3); self.sp_stock.setRange(0, 1e12); self.sp_stock.setValue(0)
        self.sp_min   = QDoubleSpinBox(); self.sp_min.setDecimals(3);   self.sp_min.setRange(0, 1e12);   self.sp_min.setValue(0)
        form.addRow("품목*", self.ed_name)
        form.addRow("규격", self.ed_spec)
        form.addRow("현재고", self.sp_stock)
        form.addRow("안전수량", self.sp_min)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(self.on_save)
        btns.rejected.connect(self.reject)
        self.saved_id = None

    def on_save(self):
        name = self.ed_name.text().strip()
        if not name:
            QMessageBox.warning(self, "경고", "품목명을 입력하세요."); return
        try:
            c = add_consumable(
                name=name,
                spec=self.ed_spec.text().strip(),
                stock_qty=self.sp_stock.value(),
                min_qty=self.sp_min.value()
            )
            self.saved_id = c.id
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))
