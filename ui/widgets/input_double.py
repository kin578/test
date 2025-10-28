from __future__ import annotations
from PySide6.QtWidgets import QDialog, QGridLayout, QDoubleSpinBox, QDialogButtonBox
from PySide6.QtCore import Qt

class QInputDialogWithDouble(QDialog):
    """
    소수 지원 수량 입력 다이얼로그.
    사용법:
        val, ok = QInputDialogWithDouble.getDouble(self, "수량 입력", "수량:", 1.0, -1e9, 1e9, 3)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("수량 입력")
        layout = QGridLayout(self)

        self.spin = QDoubleSpinBox()
        self.spin.setDecimals(3)
        self.spin.setRange(-1e12, 1e12)
        self.spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout.addWidget(self.spin, 0, 0, 1, 2)
        layout.addWidget(btns, 1, 1)

    @staticmethod
    def getDouble(parent, title, label, value, minv, maxv, decimals):
        dlg = QInputDialogWithDouble(parent)
        dlg.setWindowTitle(title or "값 입력")
        dlg.spin.setValue(value)
        dlg.spin.setDecimals(decimals)
        dlg.spin.setRange(minv, maxv)
        ok = dlg.exec() == QDialog.Accepted
        return dlg.spin.value(), ok
