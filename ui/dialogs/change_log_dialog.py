from __future__ import annotations
from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt
from sqlalchemy import select, desc, and_

from db import session_scope
from models import ChangeLog  # 프로젝트의 실제 모델


# ─────────────────────────────────────────────────────────────
# 유틸: ChangeLog 모델에 '있는' 첫 번째 컬럼 속성 반환
def _col(*names):
    for n in names:
        if hasattr(ChangeLog, n):
            return getattr(ChangeLog, n)
    return None


class ChangeLogDialog(QDialog):
    """
    다양한 스키마(컬럼명)에도 자동 대응하는 변경이력 뷰어.

    데이터 컬럼 후보:
    - 시간: changed_at / created_at / ts / timestamp
    - 사용자: changed_by / user / username / author (없으면 숨김)
    - 필드: field / column / attr (없으면 숨김)
    - 이전값: old_value / before / old / prev_value (없으면 숨김)
    - 이후값: new_value / after / new / cur_value (없으면 숨김)

    where 필터 컬럼 후보(있는 것만 사용):
    - 이름: table_name / module / table / entity
    - ID  : record_id / target_id / entity_id / equipment_id
    - 코드: record_code / code / target_code / equipment_code / key / record_key
    """
    def __init__(self, table_name: str, record_id: int, parent=None, record_code: Optional[str] = None):
        super().__init__(parent)
        self.table_name = table_name
        self.record_id = int(record_id)
        self.record_code = record_code

        self.setWindowTitle(f"변경 이력 - {table_name} #{record_id}")
        self.resize(900, 520)

        v = QVBoxLayout(self)

        # 상단 바
        top = QHBoxLayout()
        title = f"대상: {table_name} / ID={record_id}"
        if record_code:
            title += f" (코드: {record_code})"
        top.addWidget(QLabel(title))
        top.addStretch(1)
        btn_refresh = QPushButton("새로고침")
        btn_close = QPushButton("닫기")
        btn_refresh.clicked.connect(self.refresh)
        btn_close.clicked.connect(self.accept)
        top.addWidget(btn_refresh)
        top.addWidget(btn_close)
        v.addLayout(top)

        # 사용할 컬럼 자동 감지
        self.col_time  = _col("changed_at", "created_at", "ts", "timestamp")
        self.col_user  = _col("changed_by", "user", "username", "author")
        self.col_field = _col("field", "column", "attr")
        self.col_old   = _col("old_value", "before", "old", "prev_value")
        self.col_new   = _col("new_value", "after", "new", "cur_value")

        # 머리글/SELECT 컬럼 동적 구성(존재하는 것만)
        self.headers, self.select_cols = [], []
        if self.col_time:  self.headers.append("시간");   self.select_cols.append(self.col_time)
        if self.col_user:  self.headers.append("사용자"); self.select_cols.append(self.col_user)
        if self.col_field: self.headers.append("필드");   self.select_cols.append(self.col_field)
        if self.col_old:   self.headers.append("이전");   self.select_cols.append(self.col_old)
        if self.col_new:   self.headers.append("이후");   self.select_cols.append(self.col_new)

        # 최소 1개는 있어야 함(시간 우선)
        if not self.select_cols:
            fallback_col = self.col_time or list(ChangeLog.__table__.columns)[0]
            self.headers = ["시간"]
            self.select_cols = [fallback_col]

        # 테이블
        self.table = QTableWidget(0, len(self.headers), self)
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setWordWrap(True)
        self.table.setSortingEnabled(True)

        hh: QHeaderView = self.table.horizontalHeader()
        for i in range(len(self.headers)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents if i <= 2 else QHeaderView.Stretch)

        v.addWidget(self.table)
        self.refresh()

    # ─────────────────────────────────────────────────────────
    def _fetch_rows(self) -> List[Tuple]:
        # where 조건 컬럼 자동 감지
        name_col = _col("table_name", "module", "table", "entity")
        id_col   = _col("record_id", "target_id", "entity_id", "equipment_id")
        code_col = _col("record_code", "code", "target_code", "equipment_code", "key", "record_key")

        # 조합별로 차례대로 시도(첫 번째로 결과 나오는 쿼리를 사용)
        combos = []
        if name_col is not None and id_col is not None:
            combos.append(and_(name_col == self.table_name, id_col == self.record_id))
        if name_col is not None and code_col is not None and self.record_code:
            combos.append(and_(name_col == self.table_name, code_col == self.record_code))
        if id_col is not None:
            combos.append(id_col == self.record_id)
        if code_col is not None and self.record_code:
            combos.append(code_col == self.record_code)
        if name_col is not None:
            combos.append(name_col == self.table_name)
        if not combos:  # 아무 필터 컬럼도 없으면 전체(디버그용)
            combos.append(None)

        order_col = self.col_time or _col("id") or self.select_cols[0]

        with session_scope() as s:
            for cond in combos:
                stmt = select(*self.select_cols)
                if cond is not None:
                    stmt = stmt.where(cond)
                stmt = stmt.order_by(desc(order_col))
                rows = s.execute(stmt).all()
                if rows:
                    return [tuple(r) for r in rows]
            return []

    def refresh(self):
        self.table.setSortingEnabled(False)
        try:
            rows = self._fetch_rows()
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
            self.table.setRowCount(0)
            self.table.setSortingEnabled(True)
            return

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for c, val in enumerate(row):
                it = QTableWidgetItem("" if val is None else str(val))
                it.setTextAlignment((Qt.AlignCenter if c <= 2 else Qt.AlignLeft) | Qt.AlignVCenter)
                self.table.setItem(i, c, it)

        self.table.setSortingEnabled(True)
