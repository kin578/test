# ui/dialogs/equipment_edit_dialog.py
from __future__ import annotations
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QPushButton, QMessageBox, QWidget, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QComboBox
)
from sqlalchemy import select

from db import session_scope
from models import Equipment, ChangeLog
from services.equipment_service import ensure_equipment_folder, get_equipment_by_code
from services.accessory_service import list_accessories, replace_accessories
from ui.dialogs.change_log_dialog import ChangeLogDialog  # 변경이력 보기


def _to_float(s: str | None) -> Optional[float]:
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except Exception:
        return None


def _snap_equipment(e: Equipment | object) -> dict:
    return dict(
        id=getattr(e, "id", None),
        code=getattr(e, "code", "") or "",
        name=getattr(e, "name", "") or "",
        alt_name=getattr(e, "alt_name", "") or "",
        model=getattr(e, "model", "") or "",
        size_mm=getattr(e, "size_mm", "") or "",
        voltage=getattr(e, "voltage", "") or "",
        power_kwh=(getattr(e, "power_kwh", None)),
        maker=getattr(e, "maker", "") or "",
        maker_phone=getattr(e, "maker_phone", "") or "",
        in_year=getattr(e, "in_year", None),
        in_month=getattr(e, "in_month", None),
        in_day=getattr(e, "in_day", None),
        purchase_price=(getattr(e, "purchase_price", None)),
        location=getattr(e, "location", "") or "",
        purpose=getattr(e, "purpose", "") or "",       # ← 용도 (수정)
        util_other=getattr(e, "util_other", "") or "", # 유틸리티 기타(분리 유지)
        note=getattr(e, "note", "") or "",
        part=getattr(e, "part", "") or "",
        qty=getattr(e, "qty", None),
        status=getattr(e, "status", None),
    )


def _current_user() -> str | None:
    try:
        import user_session
        u = user_session.get_current_user()
        return getattr(u, "name", None)
    except Exception:
        return None


class EquipmentEditDialog(QDialog):
    ACC_ROWS = 7

    def __init__(self, code: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("설비 편집")
        self.setModal(True)
        self._original_code = code
        self.data: dict = {}
        self._acc_snapshot: list[tuple[str, str, str]] = []
        self._build_ui()
        self._load(code)

    def _build_ui(self):
        v = QVBoxLayout(self)

        form = QFormLayout()
        self.ed_code = QLineEdit()
        self.ed_name = QLineEdit()
        self.ed_alt_name = QLineEdit()
        self.ed_model = QLineEdit()
        self.ed_size = QLineEdit()
        self.ed_voltage = QLineEdit()
        self.sp_power = QDoubleSpinBox()
        self.sp_power.setRange(-1e6, 1e6)
        self.sp_power.setDecimals(3)
        self.ed_maker = QLineEdit()
        self.ed_maker_phone = QLineEdit()
        self.sp_in_year = QSpinBox()
        self.sp_in_year.setRange(0, 9999)
        self.sp_in_month = QSpinBox()
        self.sp_in_month.setRange(0, 12)
        self.sp_in_day = QSpinBox()
        self.sp_in_day.setRange(0, 31)
        self.sp_price = QLineEdit()
        self.ed_location = QLineEdit()
        self.ed_purpose = QLineEdit()   # ← 용도(purpose)
        self.ed_note = QLineEdit()      # ← 특이사항(note)
        self.ed_part = QLineEdit()

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["", "가동", "유휴", "매각", "이전"])

        form.addRow("설비번호", self.ed_code)
        form.addRow("설비명", self.ed_name)
        form.addRow("설비명(변경안)", self.ed_alt_name)
        form.addRow("모델명", self.ed_model)
        form.addRow("크기(mm)", self.ed_size)
        form.addRow("전압", self.ed_voltage)
        form.addRow("전력용량(kW)", self.sp_power)
        form.addRow("제조회사", self.ed_maker)
        form.addRow("제조회사 전화", self.ed_maker_phone)
        form.addRow("입고년도", self.sp_in_year)
        form.addRow("입고월", self.sp_in_month)
        form.addRow("입고일", self.sp_in_day)
        form.addRow("구입가격(₩)", self.sp_price)
        form.addRow("설치장소", self.ed_location)
        form.addRow("용도", self.ed_purpose)        # ← purpose
        form.addRow("비고/특이사항", self.ed_note)   # note
        form.addRow("파트", self.ed_part)
        form.addRow("상태", self.cmb_status)
        v.addLayout(form)

        acc_box = QGroupBox("부속 기구 (최대 7행)")
        acc_lay = QVBoxLayout(acc_box)
        self.tbl_acc = QTableWidget(self.ACC_ROWS, 4)
        self.tbl_acc.setHorizontalHeaderLabels(["No", "품명", "규격", "비고"])
        self.tbl_acc.verticalHeader().setVisible(False)
        hh = self.tbl_acc.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        self._reset_accessory_table()
        acc_lay.addWidget(self.tbl_acc)
        tip = QLabel("※ 비워둔 행은 저장 시 무시됩니다.")
        tip.setStyleSheet("color:#666;")
        acc_lay.addWidget(tip)
        v.addWidget(acc_box)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_log = QPushButton("변경이력…")  # 변경이력 팝업
        btn_ok = QPushButton("저장")
        btn_cancel = QPushButton("취소")
        row.addWidget(self.btn_log)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        v.addLayout(row)

        btn_ok.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        self.btn_log.clicked.connect(self._open_log)

    def _open_log(self):
        if not self.data.get("id"):
            QMessageBox.information(self, "안내", "먼저 설비를 불러온 뒤 사용하세요.")
            return
        dlg = ChangeLogDialog("equipment", int(self.data["id"]), self, record_code=self.data.get("code"))
        dlg.exec()

    def _reset_accessory_table(self):
        self.tbl_acc.blockSignals(True)
        self.tbl_acc.clearContents()
        for r in range(self.ACC_ROWS):
            self.tbl_acc.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.tbl_acc.setItem(r, 1, QTableWidgetItem(""))
            self.tbl_acc.setItem(r, 2, QTableWidgetItem(""))
            self.tbl_acc.setItem(r, 3, QTableWidgetItem(""))
        self.tbl_acc.blockSignals(False)

    def _load(self, code: str):
        e = get_equipment_by_code(code)
        if not e:
            QMessageBox.warning(self, "오류", f"설비({code})를 찾을 수 없습니다.")
            self.reject()
            return

        self.data = _snap_equipment(e)
        self.ed_code.setText(self.data.get("code", ""))
        self.ed_name.setText(self.data.get("name", ""))
        self.ed_alt_name.setText(self.data.get("alt_name", ""))
        self.ed_model.setText(self.data.get("model", ""))
        self.ed_size.setText(self.data.get("size_mm", ""))
        self.ed_voltage.setText(self.data.get("voltage", ""))
        self.sp_power.setValue(float(self.data.get("power_kwh") or 0.0))
        self.ed_maker.setText(self.data.get("maker", ""))
        self.ed_maker_phone.setText(self.data.get("maker_phone", ""))
        self.sp_in_year.setValue(int(self.data.get("in_year") or 0))
        self.sp_in_month.setValue(int(self.data.get("in_month") or 0))
        self.sp_in_day.setValue(int(self.data.get("in_day") or 0))
        price = self.data.get("purchase_price", None)
        self.sp_price.setText("" if price is None else f"{price:,.0f}")
        self.ed_location.setText(self.data.get("location", ""))
        self.ed_purpose.setText(self.data.get("purpose", ""))   # ← 용도 = purpose (수정)
        self.ed_note.setText(self.data.get("note", ""))         # 특이사항
        self.ed_part.setText(self.data.get("part", ""))
        st = (self.data.get("status") or "")
        idx = self.cmb_status.findText(st)
        self.cmb_status.setCurrentIndex(idx if idx >= 0 else 0)

        # 부속 스냅샷
        self._reset_accessory_table()
        try:
            accs = list_accessories(self.data.get("id"))
        except Exception:
            accs = []
        self._acc_snapshot = [(a.name or "", a.spec or "", a.note or "") for a in (accs or [])]
        for i, a in enumerate(accs[: self.ACC_ROWS]):
            self.tbl_acc.item(i, 1).setText(getattr(a, "name", "") or "")
            self.tbl_acc.item(i, 2).setText(getattr(a, "spec", "") or "")
            self.tbl_acc.item(i, 3).setText(getattr(a, "note", "") or "")

    def _collect_accessory_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        for r in range(self.ACC_ROWS):
            nm = (self.tbl_acc.item(r, 1).text() if self.tbl_acc.item(r, 1) else "").strip()
            sp = (self.tbl_acc.item(r, 2).text() if self.tbl_acc.item(r, 2) else "").strip()
            nt = (self.tbl_acc.item(r, 3).text() if self.tbl_acc.item(r, 3) else "").strip()
            if nm or sp or nt:
                rows.append((nm, sp, nt))
        return rows

    def _save(self):
        new_code = self.ed_code.text().strip()
        if not new_code:
            QMessageBox.warning(self, "경고", "설비번호는 필수입니다.")
            return

        # 새 값 준비
        new_vals = dict(
            code=new_code,
            name=self.ed_name.text().strip() or None,
            alt_name=self.ed_alt_name.text().strip() or None,
            model=self.ed_model.text().strip() or None,
            size_mm=self.ed_size.text().strip() or None,
            voltage=self.ed_voltage.text().strip() or None,
            power_kwh=float(self.sp_power.value()),                 # ← 0.0도 그대로 저장 (수정)
            maker=self.ed_maker.text().strip() or None,
            maker_phone=self.ed_maker_phone.text().strip() or None,
            in_year=int(self.sp_in_year.value()) or None,
            in_month=int(self.sp_in_month.value()) or None,
            in_day=int(self.sp_in_day.value()) or None,
            purchase_price=(
                float(_to_float(self.sp_price.text()) or 0.0) if self.sp_price.text().strip() else None
            ),
            location=self.ed_location.text().strip() or None,
            purpose=self.ed_purpose.text().strip() or None,         # ← 용도 = purpose (수정)
            note=self.ed_note.text().strip() or None,               # 특이사항
            part=self.ed_part.text().strip() or None,
            status=(self.cmb_status.currentText().strip() or None),
        )

        # 액세서리 수집
        rows_now = self._collect_accessory_rows()

        try:
            with session_scope() as s:
                e: Equipment | None = (
                    s.execute(
                        select(Equipment).where(
                            Equipment.code == self._original_code, Equipment.is_deleted == 0
                        )
                    )
                    .scalars()
                    .first()
                )
                if not e:
                    raise ValueError(f"설비({self._original_code})를 찾을 수 없습니다.")

                # 코드 중복 체크
                if new_vals["code"] != self._original_code:
                    dup = (
                        s.execute(select(Equipment).where(Equipment.code == new_vals["code"]))
                        .scalars()
                        .first()
                    )
                    if dup:
                        raise ValueError(f"이미 존재하는 설비번호입니다: {new_vals['code']}")

                # 변경 이력 계산
                before = self.data
                changes: dict[str, tuple[object, object]] = {}
                for k, v_new in new_vals.items():
                    v_old = before.get(k)
                    if v_old != v_new:
                        changes[k] = (v_old, v_new)

                # 실제 업데이트
                for k, v in new_vals.items():
                    setattr(e, k, v)
                s.flush()
                eq_id = int(e.id)

                # 액세서리 변경 기록
                if self._acc_snapshot != rows_now:
                    replace_accessories(eq_id, rows_now, session=s)
                    def _fmt(lst): return ", ".join([f"{a or ''}/{b or ''}/{c or ''}" for a, b, c in lst])
                    changes["accessories"] = (_fmt(self._acc_snapshot), _fmt(rows_now))

                # ChangeLog 기록
                user = _current_user()
                for field, (b, a) in changes.items():
                    s.add(
                        ChangeLog(
                            module="equipment",
                            record_id=eq_id,
                            field=field,
                            before=None if b is None else str(b),
                            after=None if a is None else str(a),
                            user=user,
                        )
                    )

            # 코드가 바뀌면 사진 폴더 이동
            if new_vals["code"] != self._original_code:
                self._try_move_photo_folder(self._original_code, new_vals["code"])

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _try_move_photo_folder(self, old_code: str, new_code: str):
        try:
            new_dir = ensure_equipment_folder(new_code)
            root_photos = os.path.dirname(new_dir)
            old_dir = os.path.join(root_photos, old_code)
            if os.path.isdir(old_dir):
                for fn in os.listdir(old_dir):
                    src = os.path.join(old_dir, fn)
                    dst = os.path.join(new_dir, fn)
                    if os.path.exists(dst):
                        base, ext = os.path.splitext(fn)
                        dst = os.path.join(new_dir, f"{base}_old{ext}")
                    try:
                        os.replace(src, dst)
                    except Exception:
                        pass
                try:
                    if not os.listdir(old_dir):
                        os.rmdir(old_dir)
                except Exception:
                    pass
        except Exception:
            pass
