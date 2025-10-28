from __future__ import annotations
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView, QCheckBox, QWidget
)
from PySide6.QtCore import Qt

class DiffMergeDialog(QDialog):
    """
    엑셀 → DB 병합 전, 변경 셀 미리보기 + 선택 적용
    rows: List[dict] 각 항목 키:
        equipment_id, code, field, old, new
    created_count: 신규 자동 추가된 개수(안내용)
    """
    def __init__(self, diffs: List[Dict[str, Any]], created_count: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("엑셀 변경사항 검토/적용")
        self.resize(1000, 600)

        self.diffs = diffs
        self.selected = [True] * len(diffs)

        root = QVBoxLayout(self)

        info = QLabel(self._make_info_text(created_count))
        info.setStyleSheet("color:#374151;")
        root.addWidget(info)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(["선택","설비코드","필드","기존값","새값","ID"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnHidden(5, True)  # 내부 ID 숨김
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        btn_all = QPushButton("모두 선택")
        btn_none = QPushButton("모두 해제")
        btn_apply = QPushButton("선택 적용")
        btn_cancel = QPushButton("취소")
        btns.addWidget(btn_all); btns.addWidget(btn_none); btns.addStretch(1)
        btns.addWidget(btn_apply); btns.addWidget(btn_cancel)
        root.addLayout(btns)

        btn_all.clicked.connect(self.select_all)
        btn_none.clicked.connect(self.select_none)
        btn_apply.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)

        self._populate()

    def _make_info_text(self, created_count:int)->str:
        parts = ["엑셀에서 변경된 셀만 선택 적용할 수 있어요."]
        if created_count:
            parts.append(f"신규 추가 {created_count}건은 이미 자동 생성되었습니다.")
        return "  •  ".join(parts)

    def _populate(self):
        self.table.setRowCount(len(self.diffs))
        for i, d in enumerate(self.diffs):
            # 체크박스
            cb = QCheckBox(); cb.setChecked(True)
            cb.stateChanged.connect(lambda state, idx=i: self._on_check(idx, state))
            w = QWidget(); lay = QHBoxLayout(w); lay.setContentsMargins(10,0,0,0)
            lay.addWidget(cb, 0, Qt.AlignLeft); lay.addStretch(1)
            self.table.setCellWidget(i, 0, w)

            def set_item(c, text, align=Qt.AlignLeft|Qt.AlignVCenter):
                it = QTableWidgetItem("" if text is None else str(text))
                it.setTextAlignment(align)
                self.table.setItem(i, c, it)

            set_item(1, d.get("code",""))
            set_item(2, d.get("field",""))
            set_item(3, d.get("old",""))
            set_item(4, d.get("new",""))
            set_item(5, d.get("equipment_id",""))

        hh = self.table.horizontalHeader()
        for col, mode in [(0, QHeaderView.ResizeToContents),
                          (1, QHeaderView.ResizeToContents),
                          (2, QHeaderView.ResizeToContents),
                          (3, QHeaderView.Interactive),
                          (4, QHeaderView.Interactive)]:
            try: hh.setSectionResizeMode(col, mode)
            except Exception: pass

    def _on_check(self, idx:int, state:int):
        self.selected[idx] = (state == Qt.Checked)

    def select_all(self):   self.selected = [True]*len(self.selected);  self._recheck(True)
    def select_none(self):  self.selected = [False]*len(self.selected); self._recheck(False)

    def _recheck(self, on:bool):
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r,0)
            if not w: continue
            cb = w.findChild(QCheckBox)
            if cb: cb.setChecked(on)

    def get_selected_diffs(self) -> List[Dict[str, Any]]:
        return [d for d, sel in zip(self.diffs, self.selected) if sel]
