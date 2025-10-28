from __future__ import annotations
import os, tempfile, inspect
from datetime import datetime

from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QDateEdit, QTextEdit,
    QDoubleSpinBox, QPushButton, QGroupBox, QScrollArea, QGridLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox, QLineEdit
)

from services.equipment_service import list_equipment
from services.consumable_service import list_consumables, low_stock_items
from services.repair_service import add_repair, update_repair, get_repair, delete_repair  # ★ 추가

# 드래그/붙여넣기용 커스텀 라벨
from ui.widgets.droppable_image_label import DroppableImageLabel


# ─────────────────────────────────────────────────────────────────────
# 공용: 함수가 받는 인자만 골라서 안전 호출 + id/rid 자동 매핑
def _call_update(func, editing_id: int | None, payload: dict):
    """
    update_repair/add_repair의 다양한 시그니처를 안전하게 처리.
    - 함수 시그니처를 읽어서 존재하는 파라미터만 전달
    - update일 때 id↔rid 자동 매핑
    """
    try:
        sig = inspect.signature(func)
        params = sig.parameters
        allowed = set(params.keys())
        filtered = {k: v for k, v in payload.items() if k in allowed}

        wants_id = "id" in allowed
        wants_rid = "rid" in allowed
        if editing_id is not None:
            if wants_id:
                filtered["id"] = editing_id
            elif wants_rid:
                filtered["rid"] = editing_id
            else:
                names = [n for n in params.keys() if params[n].kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD
                )]
                if names:
                    return func(editing_id, **filtered)
        return func(**filtered)
    except Exception:
        if editing_id is not None:
            try:
                return func(rid=editing_id, **payload)
            except TypeError:
                return func(id=editing_id, **payload)
        return func(**payload)


# ─────────────────────────────────────────────────────────────────────
# 사진 패널 유틸
def _panel_add_slot(panel):
    wrap = QWidget()
    v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0)

    lab = DroppableImageLabel()
    lab.setFixedSize(QSize(220, 160))
    lab.setAlignment(Qt.AlignCenter)
    lab.setStyleSheet("QLabel{border:1px dashed #999; background:#fafafa; color:#666;}")
    lab._orig_pix = None
    lab._current_path = None

    def set_from_path(path: str):
        px = QPixmap(path)
        if px.isNull():
            QMessageBox.warning(panel["box"], "오류", "이미지를 읽을 수 없습니다."); return
        lab._orig_pix = px
        lab._current_path = path
        lab.setPixmap(px.scaled(lab.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lab.setText("")

    def set_from_qimage(qimg: QImage):
        if qimg.isNull():
            QMessageBox.information(panel["box"], "안내", "클립보드에 이미지가 없습니다."); return
        tmp = os.path.join(tempfile.gettempdir(), f"clip_{int(datetime.now().timestamp()*1000)}.png")
        qimg.save(tmp)
        set_from_path(tmp)

    lab.on_drop_file = set_from_path
    lab.on_drop_image = set_from_qimage

    row = QHBoxLayout()
    btn_file = QPushButton("파일")
    btn_paste = QPushButton("붙여넣기")
    btn_del = QPushButton("삭제")
    row.addWidget(btn_file); row.addWidget(btn_paste); row.addWidget(btn_del); row.addStretch(1)

    def pick():
        path, _ = QFileDialog.getOpenFileName(panel["box"], "사진 선택", "", "이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if path: set_from_path(path)
    def paste():
        qi = QGuiApplication.clipboard().image()
        if qi.isNull():
            QMessageBox.information(panel["box"], "안내", "클립보드에 이미지가 없습니다."); return
        set_from_qimage(qi)
    def delete():
        idx_to_remove = None
        for idx, s in enumerate(panel["slots"]):
            if s["wrap"] is wrap:
                idx_to_remove = idx; break
        if idx_to_remove is not None:
            w = panel["slots"].pop(idx_to_remove)["wrap"]
            w.setParent(None); _panel_reflow(panel)

    btn_file.clicked.connect(pick)
    btn_paste.clicked.connect(paste)
    btn_del.clicked.connect(delete)

    v.addWidget(lab)
    v.addLayout(row)
    panel["slots"].append({"wrap": wrap, "img": lab})


def _panel_reflow(panel, cols=3):
    grid = panel["grid"]
    while grid.count():
        item = grid.takeAt(0)
        w = item.widget()
        if w: grid.removeWidget(w)
    for i, s in enumerate(panel["slots"]):
        r = i // cols; c = i % cols
        grid.addWidget(s["wrap"], r, c, 1, 1)


def make_photo_panel(title: str, default_slots=2):
    box = QGroupBox(title)
    outer = QVBoxLayout(box)
    row = QHBoxLayout()
    btn_add = QPushButton("슬롯 추가")
    btn_clear = QPushButton("전체 지우기")
    row.addWidget(btn_add); row.addWidget(btn_clear); row.addStretch(1)

    scroll = QScrollArea(); scroll.setWidgetResizable(True)
    host = QWidget(); grid = QGridLayout(host)
    grid.setContentsMargins(6,6,6,6); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)
    scroll.setWidget(host)

    outer.addLayout(row); outer.addWidget(scroll, 1)
    panel = {"box": box, "btn_add": btn_add, "btn_clear": btn_clear, "scroll": scroll, "host": host, "grid": grid, "slots": []}
    for _ in range(default_slots):
        _panel_add_slot(panel)
    _panel_reflow(panel)

    def clear_all():
        for s in panel["slots"]:
            lab: DroppableImageLabel = s["img"]
            lab._orig_pix = None; lab._current_path = None
            lab.setPixmap(QPixmap()); lab.setText("여기에\n드롭/붙여넣기")

    btn_clear.clicked.connect(clear_all)
    btn_add.clicked.connect(lambda: (_panel_add_slot(panel), _panel_reflow(panel)))
    return panel


# ─────────────────────────────────────────────────────────────────────
# 개선·수리 등록/편집 탭
class RepairTab(QWidget):
    COL_ID = 0
    COL_NAME = 1
    COL_SPEC = 2
    COL_QTY = 3
    COL_BTN = 4

    def __init__(self, on_saved_open_history):
        super().__init__()
        self.on_saved_open_history = on_saved_open_history
        self.editing_repair_id: int | None = None

        v = QVBoxLayout(self)

        # 편집 상태 표시줄
        edit_row = QHBoxLayout()
        self.lbl_edit = QLabel("")
        self.btn_new_mode = QPushButton("신규로 전환")
        self.btn_new_mode.clicked.connect(self.clear_form)
        self.btn_new_mode.setVisible(False)
        edit_row.addWidget(self.lbl_edit)

        edit_row.addStretch(1)

        # ★ 삭제 버튼(편집 모드에서만 활성)
        self.btn_delete = QPushButton("삭제")
        self.btn_delete.setVisible(False)
        self.btn_delete.clicked.connect(self._delete_current)
        edit_row.addWidget(self.btn_delete)

        edit_row.addWidget(self.btn_new_mode)
        v.addLayout(edit_row)

        # 기본 입력
        form = QFormLayout()
        self.cmb_equipment = QComboBox(); self.refresh_equipment_list()
        form.addRow("설비 선택", self.cmb_equipment)

        self.date = QDateEdit(); self.date.setDate(QDate.currentDate()); self.date.setCalendarPopup(True)
        form.addRow("진행 일자", self.date)

        self.kind = QComboBox(); self.kind.addItems(["수리","개선","점검"])
        form.addRow("구분", self.kind)

        # ★ 제목/내용 분리
        self.ed_title = QLineEdit(); self.ed_title.setPlaceholderText("제목")
        self.txt_detail = QTextEdit(); self.txt_detail.setPlaceholderText("현황 및 개선·수리 내용을 입력하세요")
        form.addRow("제목", self.ed_title)
        form.addRow("내용", self.txt_detail)

        # 수리처/수리 시간
        self.ed_vendor = QLineEdit()
        self.spn_hours = QDoubleSpinBox(); self.spn_hours.setDecimals(1); self.spn_hours.setRange(0, 1e6)
        self.spn_hours.setSingleStep(0.5); self.spn_hours.setSuffix(" 시간")
        form.addRow("수리처(이름)", self.ed_vendor)
        form.addRow("수리 시간", self.spn_hours)

        v.addLayout(form)

        # 사진
        self.before_panel = make_photo_panel("작업 전 사진", default_slots=2)
        self.after_panel  = make_photo_panel("작업 후 사진", default_slots=2)
        v.addWidget(self.before_panel["box"])
        v.addWidget(self.after_panel["box"])

        # 완료/현황
        form2 = QFormLayout()
        self.date_complete = QDateEdit(); self.date_complete.setCalendarPopup(True); self.date_complete.setDate(QDate.currentDate())
        self.cmb_progress = QComboBox(); self.cmb_progress.addItems(["진행중","완료","보류"])
        form2.addRow("완료 일자", self.date_complete)
        form2.addRow("진행 현황", self.cmb_progress)
        v.addLayout(form2)

        # 다중 소모품
        cons_box = QGroupBox("사용 소모품")
        cons_lay = QVBoxLayout(cons_box)

        row_add = QHBoxLayout()
        self.cmb_cons_add = QComboBox()
        self._refresh_consumable_combo()
        self.qty_add = QDoubleSpinBox(); self.qty_add.setDecimals(3); self.qty_add.setMinimum(0.000); self.qty_add.setMaximum(1e9); self.qty_add.setValue(1.000)
        btn_cons_add = QPushButton("추가")
        row_add.addWidget(QLabel("소모품")); row_add.addWidget(self.cmb_cons_add, 1)
        row_add.addWidget(QLabel("수량")); row_add.addWidget(self.qty_add)
        row_add.addWidget(btn_cons_add)
        cons_lay.addLayout(row_add)

        btn_row = QHBoxLayout()
        self.btn_cons_del = QPushButton("선택행 삭제")
        self.btn_cons_clear = QPushButton("전체 비우기")
        btn_row.addWidget(self.btn_cons_del); btn_row.addWidget(self.btn_cons_clear); btn_row.addStretch(1)
        cons_lay.addLayout(btn_row)

        self.tbl_cons = QTableWidget(0, 5)
        self.tbl_cons.setHorizontalHeaderLabels(["ID","품목","규격","수량",""])
        self.tbl_cons.verticalHeader().setVisible(False)
        self.tbl_cons.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_cons.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_cons.setSelectionMode(QAbstractItemView.SingleSelection)
        hh = self.tbl_cons.horizontalHeader()
        hh.setSectionResizeMode(self.COL_ID,   QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_SPEC, QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_QTY,  QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_BTN,  QHeaderView.ResizeToContents)
        self.tbl_cons.setColumnHidden(self.COL_ID, True)
        cons_lay.addWidget(self.tbl_cons)
        v.addWidget(cons_box)

        btn_cons_add.clicked.connect(self._add_consumable_row)
        self.btn_cons_del.clicked.connect(self._delete_selected_consumable)
        self.btn_cons_clear.clicked.connect(lambda: self.tbl_cons.setRowCount(0))

        # 저장
        self.btn_save = QPushButton("저장")
        v.addWidget(self.btn_save, alignment=Qt.AlignRight)
        self.btn_save.clicked.connect(self.save)

    # 폼 초기화(신규)
    def clear_form(self):
        self.editing_repair_id = None
        self.lbl_edit.setText("")
        self.btn_new_mode.setVisible(False)
        self.btn_delete.setVisible(False)   # ★ 숨김
        self.btn_save.setText("저장")
        self.date.setDate(QDate.currentDate())
        self.kind.setCurrentIndex(0)
        self.ed_title.clear()
        self.txt_detail.clear()
        self.cmb_progress.setCurrentIndex(0)
        self.date_complete.setDate(QDate.currentDate())
        self.tbl_cons.setRowCount(0)
        self.ed_vendor.setText("")
        self.spn_hours.setValue(0.0)
        for panel in (self.before_panel, self.after_panel):
            for s in panel["slots"]:
                lab: DroppableImageLabel = s["img"]
                lab._orig_pix = None; lab._current_path = None
                lab.setPixmap(QPixmap()); lab.setText("여기에\n드롭/붙여넣기")

    # 외부에서 설비 자동 선택 (ID)
    def set_active_equipment(self, equipment_id: int):
        self.refresh_equipment_list()
        idx = self.cmb_equipment.findData(equipment_id)
        if idx >= 0:
            self.cmb_equipment.setCurrentIndex(idx)

    # 외부에서 설비 자동 선택 (CODE)
    def set_active_equipment_by_code(self, code: str):
        if not code: return
        self.refresh_equipment_list()
        for i in range(self.cmb_equipment.count()):
            if self.cmb_equipment.itemText(i).startswith(str(code)):
                self.cmb_equipment.setCurrentIndex(i); break

    # 이력카드 → 편집 모드로 열기
    def open_for_edit(self, repair_id:int, equipment_id:int):
        self.clear_form()
        self.set_active_equipment(equipment_id)
        r = get_repair(repair_id)
        if not r:
            QMessageBox.warning(self, "안내", f"수리 #{repair_id} 를 찾을 수 없습니다."); return

        self.editing_repair_id = r.id
        self.lbl_edit.setText(f"편집 중: #{r.id}")
        self.btn_new_mode.setVisible(True)
        self.btn_delete.setVisible(True)    # ★ 보이기
        self.btn_save.setText("수정 저장")

        self.date.setDate(QDate(r.work_date.year, r.work_date.month, r.work_date.day))
        self.kind.setCurrentText(r.kind or "수리")
        self.ed_title.setText(r.title or "")
        self.txt_detail.setPlainText(r.detail or "")
        if r.complete_date:
            cd = r.complete_date
            self.date_complete.setDate(QDate(cd.year, cd.month, cd.day))
        self.cmb_progress.setCurrentText(r.progress_status or "진행중")
        self.ed_vendor.setText(getattr(r, "vendor", "") or "")
        try:
            self.spn_hours.setValue(float(getattr(r, "work_hours", 0.0) or 0.0))
        except Exception:
            self.spn_hours.setValue(0.0)

        self.tbl_cons.setRowCount(0)
        for it in getattr(r, "items", []) or []:
            try:
                self._add_consumable_row_direct(it.consumable_id, it.qty)
            except Exception:
                pass

    # ✅ HistoryTab → MainWindow → 여기로 연결되는 래퍼
    def open_record(self, repair_id: int, equipment_id: int):
        self.open_for_edit(repair_id, equipment_id)
        try:
            self.txt_detail.setFocus(Qt.TabFocusReason)
        except Exception:
            pass

    def refresh_equipment_list(self):
        cur = self.cmb_equipment.currentData()
        self.cmb_equipment.clear()
        for e in list_equipment(""):
            self.cmb_equipment.addItem(f"{e.code} - {e.name}", e.id)
        if cur:
            idx = self.cmb_equipment.findData(cur)
            if idx >= 0: self.cmb_equipment.setCurrentIndex(idx)

    def _refresh_consumable_combo(self):
        self.cmb_cons_add.clear()
        for c in list_consumables(""):
            self.cmb_cons_add.addItem(f"{c.name} / {c.spec or ''} (재고:{c.stock_qty})", c.id)

    def _find_row_by_cid(self, cid:int) -> int:
        for r in range(self.tbl_cons.rowCount()):
            it_id = self.tbl_cons.item(r, self.COL_ID)
            if it_id and it_id.text().isdigit() and int(it_id.text()) == cid:
                return r
        return -1

    def _add_consumable_row_direct(self, cid:int, qty:float):
        name, spec = "", ""
        for c in list_consumables(""):
            if c.id == cid:
                name, spec = c.name or "", c.spec or ""
                break

        row = self.tbl_cons.rowCount()
        self.tbl_cons.insertRow(row)
        self.tbl_cons.setItem(row, self.COL_ID, QTableWidgetItem(str(int(cid))))
        self.tbl_cons.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.tbl_cons.setItem(row, self.COL_SPEC, QTableWidgetItem(spec))

        sp = QDoubleSpinBox(); sp.setDecimals(3); sp.setMinimum(0.000); sp.setMaximum(1e12); sp.setValue(float(qty))
        self.tbl_cons.setCellWidget(row, self.COL_QTY, sp)

        btn_del = QPushButton("삭제")
        btn_del.clicked.connect(lambda _=None, b=btn_del: self._delete_cons_row_by_button(b))
        self.tbl_cons.setCellWidget(row, self.COL_BTN, btn_del)

    def _add_consumable_row(self):
        cid = self.cmb_cons_add.currentData()
        if not cid:
            QMessageBox.information(self, "안내", "소모품을 선택하세요."); return
        qty = float(self.qty_add.value())
        if qty <= 0:
            QMessageBox.warning(self, "경고", "수량은 0보다 커야 합니다."); return

        r = self._find_row_by_cid(int(cid))
        if r >= 0:
            w: QDoubleSpinBox = self.tbl_cons.cellWidget(r, self.COL_QTY)
            w.setValue(w.value() + qty)
            return

        self._add_consumable_row_direct(int(cid), qty)

    def _delete_cons_row_by_button(self, btn: QPushButton):
        for r in range(self.tbl_cons.rowCount()):
            if self.tbl_cons.cellWidget(r, self.COL_BTN) is btn:
                self.tbl_cons.removeRow(r)
                break

    def _delete_selected_consumable(self):
        r = self.tbl_cons.currentRow()
        if r >= 0:
            self.tbl_cons.removeRow(r)
        else:
            QMessageBox.information(self, "안내", "삭제할 행을 선택하세요.")

    def _collect_paths(self, panel) -> list[str]:
        arr = []
        for s in panel["slots"]:
            p = getattr(s["img"], "_current_path", None)
            if p: arr.append(p)
        return arr

    def _gather_used_items(self):
        items = []
        for r in range(self.tbl_cons.rowCount()):
            it_id = self.tbl_cons.item(r, self.COL_ID)
            if not it_id: continue
            cid = int(it_id.text())
            w: QDoubleSpinBox = self.tbl_cons.cellWidget(r, self.COL_QTY)
            qty = float(w.value()) if w else 0.0
            if qty > 0:
                items.append((cid, qty))
        return items or None

    def _current_code(self) -> str:
        txt = self.cmb_equipment.currentText()
        return txt.split(" - ", 1)[0] if txt else ""

    def _delete_current(self):
        if not self.editing_repair_id:
            QMessageBox.information(self, "안내", "삭제할 수리 내역이 없습니다."); return
        rid = int(self.editing_repair_id)
        code = self._current_code()
        yn = QMessageBox.question(self, "확인", f"수리 내역 #{rid} 를 삭제할까요?\n(사용된 소모품 재고는 자동 복원됩니다)")
        if yn != QMessageBox.Yes:
            return
        try:
            delete_repair(rid, reverse_stock=True)
            QMessageBox.information(self, "완료", "삭제되었습니다.")
            # 히스토리 탭 최신화
            if callable(self.on_saved_open_history) and code:
                self.on_saved_open_history(code)
            self.clear_form()
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def save(self):
        eid = self.cmb_equipment.currentData()
        if not eid: QMessageBox.warning(self, "경고", "설비를 선택하세요."); return
        d = self.date.date().toPython()
        k = self.kind.currentText()
        title = self.ed_title.text().strip()
        detail = self.txt_detail.toPlainText().strip()
        if not detail:
            QMessageBox.warning(self, "경고", "내용을 입력하세요."); return

        items = self._gather_used_items()
        before_files = self._collect_paths(self.before_panel)
        after_files  = self._collect_paths(self.after_panel)
        vendor_name = self.ed_vendor.text().strip() or None
        work_hours  = float(self.spn_hours.value())

        payload = dict(
            equipment_id=eid, work_date=d, kind=k,
            title=title, detail=detail, items=items,
            complete_date=self.date_complete.date().toPython(),
            progress_status=self.cmb_progress.currentText(),
            vendor=vendor_name, work_hours=work_hours,
            before_files=before_files, after_files=after_files,
        )

        try:
            if self.editing_repair_id:
                _call_update(update_repair, self.editing_repair_id, payload)
                QMessageBox.information(self, "완료", "수정되었습니다.")
            else:
                _call_update(add_repair, None, payload)
                QMessageBox.information(self, "완료", "저장되었습니다.")

            lows = low_stock_items()
            if lows:
                names = "\n".join([f"- {x.name} / {x.spec or ''} (재고:{x.stock_qty}, 안전:{getattr(x,'min_qty',0)})" for x in lows])
                QMessageBox.warning(self, "소모품 부족 알림", f"아래 품목이 안전수량 미만입니다:\n\n{names}")

            if callable(self.on_saved_open_history):
                code = self._current_code()
                if code:
                    self.on_saved_open_history(code)

            self.clear_form()

        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
