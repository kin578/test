from __future__ import annotations
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout,
    QDialog, QDialogButtonBox, QDoubleSpinBox, QAbstractItemView,
    QLabel, QFileDialog, QMessageBox, QComboBox, QDateEdit, QCheckBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QDate
import os

try:
    from ui.widgets.input_double import QInputDialogWithDouble
except Exception:
    class QInputDialogWithDouble(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("수량 입력")
            lay = QVBoxLayout(self)
            self.spin = QDoubleSpinBox(); self.spin.setDecimals(3)
            self.spin.setRange(-1e12, 1e12)
            lay.addWidget(self.spin)
            btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            lay.addWidget(btns)
            btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        @staticmethod
        def getDouble(parent, title, label, value, minv, maxv, decimals):
            dlg = QInputDialogWithDouble(parent)
            dlg.setWindowTitle(title); dlg.spin.setValue(value)
            dlg.spin.setDecimals(decimals); dlg.spin.setRange(minv, maxv)
            ok = dlg.exec() == QDialog.Accepted
            return dlg.spin.value(), ok

from services.consumable_service import (
    list_consumables, upsert_consumable, delete_consumable,
    adjust_stock, zero_out_stock, export_consumables_xlsx,
    save_consumable_template_xlsx, save_consumable_txn_template_xlsx
)
from services.export_consumable_txn import export_consumable_txn_xlsx
from services import reason_code_service as rcs

from settings import get_start_dir, update_last_save_dir

def _start_file(suggest_name: str) -> str:
    return os.path.join(get_start_dir(), suggest_name)

# ───────── 사유 선택 다이얼로그(표준코드) ─────────
class ReasonCodeDialog(QDialog):
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("출고 사유 (표준코드)")
        v = QVBoxLayout(self)

        self.list = QListWidget()
        self.list.setSelectionMode(self.list.SingleSelection)
        v.addWidget(self.list)

        btns_row = QHBoxLayout()
        self.btn_add = QPushButton("추가")
        self.btn_del = QPushButton("삭제")
        self.btn_fav = QPushButton("즐겨찾기 토글")
        btns_row.addWidget(self.btn_add); btns_row.addWidget(self.btn_del); btns_row.addWidget(self.btn_fav); btns_row.addStretch(1)
        v.addLayout(btns_row)

        self.ed_custom = QLineEdit(initial_text)
        self.ed_custom.setPlaceholderText("직접 입력(새 코드로 추가 가능)")
        v.addWidget(self.ed_custom)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v.addWidget(bb)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_fav.clicked.connect(self._on_fav)

        self._reload()

    def _reload(self):
        self.list.clear()
        rows = rcs.list_reason_codes()
        for r in rows:
            item = QListWidgetItem(("★ " if r["favorite"] else "☆ ") + r["name"])
            item.setData(Qt.UserRole, r)
            self.list.addItem(item)

    def _current_row(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _on_add(self):
        txt = (self.ed_custom.text() or "").strip()
        if not txt:
            QMessageBox.information(self, "안내", "내용을 입력하세요."); return
        rcs.add_reason_code(txt, favorite=False)
        self.ed_custom.clear(); self._reload()

    def _on_del(self):
        r = self._current_row()
        if not r: return
        if QMessageBox.question(self, "삭제", f"삭제할까요?\n{r['name']}") != QMessageBox.Yes:
            return
        rcs.delete_reason_code(int(r["id"])); self._reload()

    def _on_fav(self):
        r = self._current_row()
        if not r: return
        rcs.toggle_favorite(int(r["id"])); self._reload()

    def value(self) -> str:
        r = self._current_row()
        if r: return r["name"]
        return (self.ed_custom.text() or "").strip()

# ───────── 편집/메인 탭 ─────────
class ConsumableEditDialog(QDialog):
    def __init__(self, parent=None, cid: int | None = None, name="", spec="", min_qty=0.0, note="", stock_qty=None):
        super().__init__(parent)
        self.setWindowTitle("소모품 편집")
        self.cid = cid
        form = QFormLayout(self)
        self.ed_name = QLineEdit(name)
        self.ed_spec = QLineEdit(spec)
        self.sp_min = QDoubleSpinBox(); self.sp_min.setDecimals(3); self.sp_min.setRange(0, 1e12); self.sp_min.setValue(float(min_qty or 0.0))
        self.ed_note = QLineEdit(note or "")
        self.sp_stock = QDoubleSpinBox(); self.sp_stock.setDecimals(3); self.sp_stock.setRange(0, 1e12)
        if stock_qty is not None:
            self.sp_stock.setValue(float(stock_qty))
        else:
            self.sp_stock.setSpecialValueText("(유지)")
            self.sp_stock.setMinimum(0.0); self.sp_stock.setValue(0.0)
        form.addRow("품목", self.ed_name)
        form.addRow("규격", self.ed_spec)
        form.addRow("안전수량", self.sp_min)
        form.addRow("비고", self.ed_note)
        form.addRow("현재고", self.sp_stock)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        form.addRow(btns)

    def data(self):
        return dict(
            cid=self.cid,
            name=self.ed_name.text().strip(),
            spec=self.ed_spec.text().strip(),
            min_qty=float(self.sp_min.value()),
            note=self.ed_note.text().strip(),
            stock_qty=float(self.sp_stock.value()),
        )

class ConsumableTab(QWidget):
    COL_ID = 0; COL_NAME = 1; COL_SPEC = 2; COL_STOCK = 3; COL_MIN = 4; COL_NOTE = 5

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)

        tl = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("소모품명/규격 검색...")
        btn_search = QPushButton("검색")
        btn_new = QPushButton("신규"); btn_edit = QPushButton("수정"); btn_del = QPushButton("삭제")
        btn_zero = QPushButton("재고 0으로"); btn_in = QPushButton("입고(+)")
        btn_out = QPushButton("출고(-)")
        btn_imp = QPushButton("엑셀 가져오기"); btn_exp = QPushButton("엑셀 내보내기")
        btn_txn_exp = QPushButton("이력 내보내기"); btn_txn_tmpl = QPushButton("입출고 샘플")
        for w in (self.search, btn_search, btn_new, btn_edit, btn_del, btn_zero, btn_in, btn_out, btn_imp, btn_exp, btn_txn_exp, btn_txn_tmpl):
            tl.addWidget(w)
        tl.addStretch(1); v.addLayout(tl)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "품목", "규격", "현재고", "안전수량", "비고"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_SPEC, QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_STOCK, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_MIN, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NOTE, QHeaderView.Stretch)
        self.table.setColumnHidden(self.COL_ID, True)
        v.addWidget(self.table)

        btn_search.clicked.connect(self.refresh); self.search.returnPressed.connect(self.refresh)
        btn_new.clicked.connect(self.new_item); btn_edit.clicked.connect(self.edit_item); btn_del.clicked.connect(self.delete_item)
        btn_zero.clicked.connect(self.zero_item)
        btn_in.clicked.connect(lambda: self.adjust_item(True))
        btn_out.clicked.connect(lambda: self.adjust_item(False))
        btn_imp.clicked.connect(self.import_excel)
        btn_exp.clicked.connect(self.export_excel)
        btn_txn_exp.clicked.connect(self.export_txn_excel)
        btn_txn_tmpl.clicked.connect(self.save_txn_template)

        self.refresh()

    def selected_row(self) -> int: return self.table.currentRow()
    def selected_id(self) -> int | None:
        r = self.selected_row()
        if r < 0: return None
        it = self.table.item(r, self.COL_ID)
        return int(it.text()) if it and it.text().isdigit() else None

    def refresh(self):
        rows = list_consumables(self.search.text())
        self.table.setRowCount(len(rows))
        for i, c in enumerate(rows):
            def put(col, txt, align=Qt.AlignLeft | Qt.AlignVCenter):
                it = QTableWidgetItem("" if txt is None else str(txt))
                it.setTextAlignment(align); self.table.setItem(i, col, it)
            put(self.COL_ID, c.id, Qt.AlignCenter)
            put(self.COL_NAME, c.name)
            put(self.COL_SPEC, c.spec)
            put(self.COL_STOCK, c.stock_qty, Qt.AlignRight | Qt.AlignVCenter)
            put(self.COL_MIN, c.min_qty, Qt.AlignRight | Qt.AlignVCenter)
            put(self.COL_NOTE, c.note)

    def new_item(self):
        dlg = ConsumableEditDialog(self, None, "", "", 0.0, "", 0.0)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.data()
            try:
                upsert_consumable(name=d["name"], spec=d["spec"], min_qty=d["min_qty"], note=d["note"], stock_qty=d["stock_qty"])
                QMessageBox.information(self, "완료", "등록되었습니다."); self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "에러", str(e))

    def edit_item(self):
        cid = self.selected_id()
        if not cid:
            QMessageBox.information(self, "안내", "수정할 항목을 선택하세요."); return
        r = self.selected_row()
        name = self.table.item(r, self.COL_NAME).text()
        spec = self.table.item(r, self.COL_SPEC).text()
        stock = float(self.table.item(r, self.COL_STOCK).text() or 0.0)
        minq = float(self.table.item(r, self.COL_MIN).text() or 0.0)
        note = self.table.item(r, self.COL_NOTE).text()
        dlg = ConsumableEditDialog(self, cid, name, spec, minq, note, stock)
        if dlg.exec() == QDialog.Accepted:
            d = dlg.data()
            try:
                upsert_consumable(cid=cid, name=d["name"], spec=d["spec"], min_qty=d["min_qty"], note=d["note"], stock_qty=d["stock_qty"])
                QMessageBox.information(self, "완료", "수정되었습니다."); self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "에러", str(e))

    def delete_item(self):
        cid = self.selected_id()
        if not cid:
            QMessageBox.information(self, "안내", "삭제할 항목을 선택하세요."); return
        if QMessageBox.question(self, "확인", "선택한 소모품을 삭제할까요?") != QMessageBox.Yes:
            return
        try:
            delete_consumable(cid, force=False)
            QMessageBox.information(self, "완료", "삭제되었습니다."); self.refresh()
        except Exception as e1:
            if QMessageBox.question(self, "강제 삭제", f"{e1}\n\n입출고 이력까지 함께 삭제하고 강제 삭제할까요?") == QMessageBox.Yes:
                try:
                    delete_consumable(cid, force=True)
                    QMessageBox.information(self, "완료", "강제 삭제되었습니다."); self.refresh()
                except Exception as e2:
                    QMessageBox.critical(self, "에러", str(e2))

    def zero_item(self):
        cid = self.selected_id()
        if not cid:
            QMessageBox.information(self, "안내", "대상을 선택하세요."); return
        try:
            zero_out_stock(cid)
            QMessageBox.information(self, "완료", "재고를 0으로 맞췄습니다."); self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def adjust_item(self, is_in: bool):
        cid = self.selected_id()
        if not cid:
            QMessageBox.information(self, "안내", "대상을 선택하세요."); return
        qty, ok = QInputDialogWithDouble.getDouble(self, "수량 입력", "수량:", 1.0, -1e12, 1e12, 3)
        if not ok: return
        if not is_in and qty > 0:
            qty = -qty

        # 표준 사유 코드 사용(출고 시 필수 권장)
        reason_text = "입고"
        if qty < 0:
            dlg = ReasonCodeDialog(self, initial_text="수리 사용")
            if dlg.exec() != QDialog.Accepted:
                return
            reason_text = dlg.value() or "출고"

        try:
            adjust_stock(cid, qty=qty, reason=reason_text)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    # 엑셀(목록/이력)
    def import_excel(self):
        from services.importer import import_consumables_xlsx, ensure_db
        path, _ = QFileDialog.getOpenFileName(self, "소모품 엑셀 선택", "", "Excel Files (*.xlsx)")
        if not path: return
        try:
            ensure_db(); import_consumables_xlsx(path)
            QMessageBox.information(self, "완료", "엑셀에서 가져왔습니다."); self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 내보내기",
                                              _start_file("소모품_내보내기.xlsx"),
                                              "Excel Files (*.xlsx)")
        if not path: return
        try:
            p = export_consumables_xlsx(path)
            update_last_save_dir(os.path.dirname(p))
            QMessageBox.information(self, "완료", f"저장됨:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def export_txn_excel(self):
        dlg = QDialog(self); dlg.setWindowTitle("입출고 이력 내보내기")
        form = QFormLayout(dlg)
        dt_from = QDateEdit(); dt_from.setCalendarPopup(True); dt_from.setDate(QDate.currentDate().addMonths(-1))
        dt_to   = QDateEdit(); dt_to.setCalendarPopup(True); dt_to.setDate(QDate.currentDate())
        chk_use = QCheckBox("기간 필터 사용"); chk_use.setChecked(False)
        form.addRow(chk_use); form.addRow("시작일", dt_from); form.addRow("종료일", dt_to)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); form.addRow(btns)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted: return
        d1 = dt_from.date().toPython() if chk_use.isChecked() else None
        d2 = dt_to.date().toPython() if chk_use.isChecked() else None

        path, _ = QFileDialog.getSaveFileName(self, "입출고 이력 엑셀 저장",
                                              _start_file("소모품_입출고이력.xlsx"),
                                              "Excel Files (*.xlsx)")
        if not path: return
        try:
            out = export_consumable_txn_xlsx(keyword="", start_date=d1, end_date=d2, path=path)
            update_last_save_dir(os.path.dirname(out))
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def save_txn_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "입출고 샘플 저장",
                                              _start_file("소모품_입출고_샘플.xlsx"),
                                              "Excel Files (*.xlsx)")
        if not path: return
        try:
            p = save_consumable_txn_template_xlsx(path)
            update_last_save_dir(os.path.dirname(p))
            QMessageBox.information(self, "완료", f"저장됨:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
