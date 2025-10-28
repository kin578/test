from __future__ import annotations
import os
import shutil
import tempfile
import zipfile
from typing import List
from datetime import date as _date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
    QMainWindow, QCheckBox, QComboBox, QDateEdit
)
from PySide6.QtCore import Qt, QDate

from services.equipment_service import (
    list_equipment, add_equipment, ensure_equipment_folder, get_equipment_by_code,
    get_delete_preview, delete_equipment_by_code, update_status
)
from services.exporter import export_equipment_xlsx

# 이력카드 내보내기(연도 필터 지원)
try:
    from services.export_history_card import (
        export_history_cards_multi_xlsx,
        export_history_card_xlsx,
    )
except Exception:
    export_history_cards_multi_xlsx = None
    export_history_card_xlsx = None

# 시작 디렉터리(있으면 사용)
try:
    import settings
    def _start_dir() -> str:
        try:
            return settings.get_start_dir()
        except Exception:
            return ""
except Exception:
    settings = None
    def _start_dir() -> str: return ""

from ..dialogs.equipment_edit_dialog import EquipmentEditDialog
from ..dialogs.change_log_dialog import ChangeLogDialog


class EquipmentTab(QWidget):
    def __init__(self, on_open_history, on_search_done=None, on_edited=None):
        super().__init__()
        self.on_open_history = on_open_history
        self.on_search_done = on_search_done
        self.on_edited = on_edited
        self._user_search_trigger = False

        root = QVBoxLayout(self)

        # ── 1줄: 상태 필터 + 검색
        row1 = QHBoxLayout()
        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItems(["모두", "가동", "유휴", "매각", "이전"])
        self.cmb_status_filter.setCurrentIndex(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("모든 항목 통합 검색")
        btn_find = QPushButton("검색")

        row1.addWidget(self.cmb_status_filter, 0)
        row1.addWidget(self.search, 1)
        row1.addWidget(btn_find, 0)
        root.addLayout(row1)

        # ── 2줄: 액션 버튼들
        row2 = QHBoxLayout()
        btn_add    = QPushButton("신규 설비")
        btn_edit   = QPushButton("편집")
        btn_delete = QPushButton("삭제")
        btn_import = QPushButton("엑셀 가져오기(머지)")
        btn_export = QPushButton("엑셀로 내보내기")
        btn_export_history_multi = QPushButton("선택 이력카드(한 파일)")
        btn_export_history_each  = QPushButton("선택 이력카드(개별 파일)")  # ← ZIP으로 저장
        btn_select_all     = QPushButton("전체선택")
        btn_unselect_all   = QPushButton("전체해제")
        btn_log            = QPushButton("변경이력")

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#3a7; font-weight:600;")

        for b in [
            btn_add, btn_edit, btn_delete, btn_import, btn_export,
            btn_export_history_multi, btn_export_history_each,
            btn_select_all, btn_unselect_all, btn_log
        ]:
            row2.addWidget(b)
        row2.addStretch(1)
        row2.addWidget(self.lbl_status)
        root.addLayout(row2)

        # ── 3줄: 상태 일괄 변경 + (신규) 기준일/해당연도 옵션
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("선택 설비 상태:"))
        self.cmb_status_bulk = QComboBox()
        self.cmb_status_bulk.addItems(["가동", "유휴", "매각", "이전"])
        btn_bulk_change = QPushButton("선택 상태 변경")
        row3.addWidget(self.cmb_status_bulk)
        row3.addWidget(btn_bulk_change)

        row3.addSpacing(20)
        row3.addWidget(QLabel("기준일:"))
        self.dt_base = QDateEdit()
        self.dt_base.setCalendarPopup(True)
        self.dt_base.setDate(QDate.currentDate())  # 오늘로 기본값
        row3.addWidget(self.dt_base)

        self.btn_toggle_year = QPushButton("해당연도만: ON")
        self.btn_toggle_year.setCheckable(True)
        self.btn_toggle_year.setChecked(True)  # 기본 ON
        self.btn_toggle_year.clicked.connect(self._toggle_year_only_text)
        row3.addWidget(self.btn_toggle_year)

        row3.addStretch(1)
        root.addLayout(row3)

        # ── 테이블 (★ “용도”와 “유틸리티 기타” 분리)
        headers = [
            "설비번호","자산명","설비명","설비명 변경안","모델명",
            "크기(가로x세로x높이)mm","전압","전력용량(Kwh)","유틸리티 AIR","유틸리티 냉각수","유틸리티 진공",
            "용도","유틸리티 기타",
            "제조회사","제조회사 대표 전화번호","제조일자","입고일(년)","입고일(월)","입고일(일)","수량","구입가격","설비위치","비고","파트",
            "상태"
        ]
        self.headers = headers
        headers_with_select = ["선택"] + headers

        self.table = QTableWidget(0, len(headers_with_select))
        self.table.setHorizontalHeaderLabels(headers_with_select)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(self.open_history)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        try:
            hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        except Exception:
            pass

        root.addWidget(self.table)

        # ── 시그널
        btn_find.clicked.connect(self._on_click_search)
        self.search.returnPressed.connect(self._on_enter_search)
        self.cmb_status_filter.currentIndexChanged.connect(self._on_click_search)

        btn_add.clicked.connect(self.add_dialog)
        btn_edit.clicked.connect(self.edit_dialog)
        btn_delete.clicked.connect(self.delete_selected)
        btn_import.clicked.connect(self.import_excel)          # ← 왕복 머지 버전
        btn_export.clicked.connect(self.export_excel)
        btn_export_history_multi.clicked.connect(self.export_history_multi)
        btn_export_history_each.clicked.connect(self.export_history_each)  # ← ZIP 저장
        btn_select_all.clicked.connect(self.select_all_checkboxes)
        btn_unselect_all.clicked.connect(self.unselect_all_checkboxes)
        btn_log.clicked.connect(self.open_change_log)
        btn_bulk_change.clicked.connect(self.bulk_change_status)

        self.refresh()
        self._hide_quantity_column()

    # ────────────────────────────────
    def _toggle_year_only_text(self):
        self.btn_toggle_year.setText(f"해당연도만: {'ON' if self.btn_toggle_year.isChecked() else 'OFF'}")

    def _on_click_search(self):
        self._user_search_trigger = True
        self.refresh()

    def _on_enter_search(self):
        self._user_search_trigger = True
        self.refresh()

    def _hide_quantity_column(self):
        try:
            idx = self.headers.index("수량")
            self.table.setColumnHidden(idx + 1, True)  # "선택" 열이 0번이라 +1
        except ValueError:
            pass

    def _put_checkbox(self, row: int):
        cb = QCheckBox()
        cb.setTristate(False)
        cb.setChecked(False)
        cb.setStyleSheet("margin-left:8px;")
        self.table.setCellWidget(row, 0, cb)

    def select_all_checkboxes(self):
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if isinstance(w, QCheckBox):
                w.setChecked(True)

    def unselect_all_checkboxes(self):
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if isinstance(w, QCheckBox):
                w.setChecked(False)

    # ────────────────────────────────
    def refresh(self):
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.table.setUpdatesEnabled(False)
        rows = []
        try:
            hh = self.table.horizontalHeader()
            sort_on = self.table.isSortingEnabled()
            sort_col = hh.sortIndicatorSection()
            sort_order = hh.sortIndicatorOrder()
            self.table.setSortingEnabled(False)

            status = self.cmb_status_filter.currentText()
            rows = list_equipment(self.search.text(), status=status, include_deleted=False)

            self.table.setRowCount(len(rows))
            for i, e in enumerate(rows):
                self._put_checkbox(i)

                def S(x): return "" if x is None else str(x)
                def set_cell(irow, icol, text, align=Qt.AlignLeft | Qt.AlignVCenter):
                    it = QTableWidgetItem(text); it.setTextAlignment(align)
                    self.table.setItem(irow, icol, it)

                set_cell(i, 1, S(e.code))
                set_cell(i, 2, S(e.asset_name))
                set_cell(i, 3, S(e.name))
                set_cell(i, 4, S(e.alt_name))
                set_cell(i, 5, S(e.model))
                set_cell(i, 6, S(e.size_mm))
                set_cell(i, 7, S(e.voltage))
                set_cell(i, 8, S(e.power_kwh))
                set_cell(i, 9, S(e.util_air))
                set_cell(i,10, S(e.util_coolant))
                set_cell(i,11, S(e.util_vac))
                set_cell(i,12, S(getattr(e, "purpose", None)))     # ★ 용도
                set_cell(i,13, S(e.util_other))                    # ★ 유틸리티 기타
                set_cell(i,14, S(e.maker))
                set_cell(i,15, S(e.maker_phone))
                set_cell(i,16, S(e.manufacture_date), Qt.AlignCenter)
                set_cell(i,17, S(e.in_year), Qt.AlignCenter)
                set_cell(i,18, S(e.in_month), Qt.AlignCenter)
                set_cell(i,19, S(e.in_day), Qt.AlignCenter)
                set_cell(i,20, S(e.qty))
                set_cell(i,21, "" if e.purchase_price is None else f"{e.purchase_price:,.0f}", Qt.AlignRight | Qt.AlignVCenter)
                set_cell(i,22, S(e.location))
                note_item = QTableWidgetItem(S(e.note)); note_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                self.table.setItem(i, 23, note_item)
                set_cell(i,24, S(e.part))
                set_cell(i,25, S(getattr(e, "status", "")), Qt.AlignCenter)

            self._hide_quantity_column()
            self.table.setSortingEnabled(True)
            if sort_on:
                self.table.sortItems(sort_col, sort_order)

            self.lbl_status.setText(f"검색완료 ({len(rows)}건)")
            if isinstance(self.window(), QMainWindow):
                self.window().statusBar().showMessage(f"검색완료 ({len(rows)}건)", 2000)

        except Exception as e:
            QMessageBox.critical(self, "검색 오류", str(e))
        finally:
            self.table.setUpdatesEnabled(True)
            from PySide6.QtWidgets import QApplication
            QApplication.restoreOverrideCursor()

        if self._user_search_trigger:
            QMessageBox.information(self, "검색완료", f"{len(rows)}건 검색되었습니다.")
        self._user_search_trigger = False

        if self.on_search_done:
            self.on_search_done(self.table.rowCount())

    def update_row_by_code(self, code:str) -> bool:
        row_idx = -1
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 1)
            if it and it.text() == code:
                row_idx = r; break
        if row_idx < 0: return False
        e = get_equipment_by_code(code)
        if not e: return False

        def S(x): return "" if x is None else str(x)
        def set_cell(icol, text, align=Qt.AlignLeft|Qt.AlignVCenter):
            exist = self.table.item(row_idx, icol)
            if exist is None:
                it = QTableWidgetItem(S(text)); it.setTextAlignment(align)
                self.table.setItem(row_idx, icol, it)
            else:
                exist.setText(S(text))
                exist.setTextAlignment(align)

        set_cell(1, S(e.code)); set_cell(2, S(e.asset_name)); set_cell(3, S(e.name))
        set_cell(4, S(e.alt_name)); set_cell(5, S(e.model)); set_cell(6, S(e.size_mm))
        set_cell(7, S(e.voltage)); set_cell(8, S(e.power_kwh)); set_cell(9, S(e.util_air))
        set_cell(10, S(e.util_coolant)); set_cell(11, S(e.util_vac))
        set_cell(12, S(getattr(e, "purpose", None)))     # 용도
        set_cell(13, S(e.util_other))                    # 유틸리티 기타
        set_cell(14, S(e.maker)); set_cell(15, S(e.maker_phone))
        set_cell(16, S(e.manufacture_date), Qt.AlignCenter)
        set_cell(17, S(e.in_year), Qt.AlignCenter); set_cell(18, S(e.in_month), Qt.AlignCenter); set_cell(19, S(e.in_day), Qt.AlignCenter)
        set_cell(20, S(e.qty)); set_cell(21, "" if e.purchase_price is None else f"{e.purchase_price:,.0f}", Qt.AlignRight|Qt.AlignVCenter)
        set_cell(22, S(e.location))
        note = self.table.item(row_idx, 23)
        if note is None:
            note_item = QTableWidgetItem(S(e.note)); note_item.setTextAlignment(Qt.AlignLeft|Qt.AlignTop)
            self.table.setItem(row_idx, 23, note_item)
        else:
            note.setText(S(e.note)); note.setTextAlignment(Qt.AlignLeft|Qt.AlignTop)
        set_cell(24, S(e.part))
        set_cell(25, S(getattr(e, "status", "")), Qt.AlignCenter)
        return True

    def current_code(self, row:int|None=None) -> str|None:
        if row is None: row = self.table.currentRow()
        if row < 0: return None
        it = self.table.item(row, 1)
        return it.text().strip() if it else None

    def open_history(self, row:int, col:int):
        code = self.current_code(row)
        if code: self.on_open_history(code)

    # ── 상태 일괄 변경(항상 단건 호출로 루프)
    def bulk_change_status(self):
        status = self.cmb_status_bulk.currentText().strip()
        codes = self._gather_checked_codes()
        if not codes:
            c = self.current_code()
            if c: codes = [c]
        if not codes:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하거나 체크하세요.")
            return

        ok, fail, errs = 0, 0, []
        for c in codes:
            try:
                update_status(c, status)
                ok += 1
            except Exception as e:
                fail += 1
                errs.append(f"{c}: {e}")

        self.refresh()
        if fail == 0:
            QMessageBox.information(self, "완료", f"{ok}건 상태를 '{status}'로 변경했습니다.")
        else:
            msg = f"완료: {ok}건, 실패: {fail}건\n\n" + "\n".join(errs[:10])
            QMessageBox.warning(self, "일부 실패", msg)

    # ── 샘플 신규/편집/삭제/엑셀
    def add_dialog(self):
        QMessageBox.information(self, "안내", "샘플로 간단 입력만 진행합니다. 이후 전용 입력폼 추가 예정입니다.")
        code = "EQ-"+str(self.table.rowCount()+1)
        add_equipment(code=code, name="새 설비")
        ensure_equipment_folder(code)
        self.refresh()

    def edit_dialog(self):
        old_code = self.current_code()
        if not old_code:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요."); return
        dlg = EquipmentEditDialog(old_code, self)
        if dlg.exec():
            new_code = dlg.ed_code.text().strip()
            from PySide6.QtWidgets import QApplication
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                if new_code == old_code:
                    self.update_row_by_code(new_code)
                    hh = self.table.horizontalHeader()
                    self.table.model().sort(hh.sortIndicatorSection(), hh.sortIndicatorOrder())
                else:
                    self.refresh()
            finally:
                QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "완료", "저장되었습니다.")
            if self.on_edited: self.on_edited(new_code)

    def import_excel(self):
        """
        엑셀 왕복 머지:
        - services/importer_diff.import_equipment_xlsx_diff 가 있으면 그걸 사용(미리보기/선택 적용)
        - 없으면 기존 importer.import_equipment_xlsx 로 폴백
        """
        start_dir = _start_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "설비관리대장 엑셀 선택", start_dir, "Excel Files (*.xlsx)"
        )
        if not path:
            return

        # 1) 가능한 경우, diff 미리보기 버전 사용
        try:
            from services.importer_diff import import_equipment_xlsx_diff
            created, diff_count, applied = import_equipment_xlsx_diff(path, parent=self)
            parts = [f"신규 추가: {created}건"]
            if diff_count:
                parts.append(f"변경 셀: {diff_count}개 중 {applied}개 적용")
            else:
                parts.append("변경된 셀 없음")
            QMessageBox.information(self, "가져오기 결과", "\n".join(parts))
            self.refresh()
            return
        except ImportError:
            # diff 모듈이 아직 없는 경우 → 기존 방식으로 폴백
            pass
        except Exception as e:
            # diff 경로가 있었지만 실행 중 실패 → 메시지 안내 후 폴백 시도
            QMessageBox.warning(self, "머지 실패", f"머지 방식 가져오기에 실패했습니다.\n기존 방식으로 시도합니다.\n\n{e}")

        # 2) 기존 가져오기(전체 갱신형)
        try:
            from services.importer import import_equipment_xlsx, ensure_db as importer_ensure_db
        except Exception as e:
            QMessageBox.critical(self, "가져오기 오류", f"importer 모듈을 찾을 수 없습니다.\n{e}")
            return

        try:
            importer_ensure_db()
            import_equipment_xlsx(path)
            QMessageBox.information(
                self, "완료",
                "기존 방식으로 가져오기가 완료되었습니다.\n"
                "※ 변경 셀만 머지하려면 services/importer_diff.py와 ui/dialogs/diff_merge_dialog.py를 추가해 주세요."
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def export_excel(self):
        start_dir = _start_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "설비관리대장 내보내기", os.path.join(start_dir, "설비관리대장.xlsx"),
            "Excel Files (*.xlsx)"
        )
        if not path: return
        try:
            p = export_equipment_xlsx(keyword=self.search.text(), path=path)
            QMessageBox.information(self, "완료", f"저장됨:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def export_history_multi(self):
        if export_history_cards_multi_xlsx is None:
            QMessageBox.information(self, "안내", "이 기능은 아직 구성되지 않았습니다."); return
        codes = self._gather_checked_codes()
        if not codes:
            QMessageBox.information(self, "안내", "체크된 설비가 없습니다."); return
        default_name = f"이력카드_묶음_{len(codes)}대.xlsx"
        start_dir = _start_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "이력카드 묶음으로 저장",
            os.path.join(start_dir, default_name),
            "Excel Files (*.xlsx)"
        )
        if not path: return
        try:
            base = self._base_date_value()
            out = export_history_cards_multi_xlsx(
                codes, path=path,
                year_only=self.btn_toggle_year.isChecked(),
                base_date=base,
            )
            QMessageBox.information(self, "완료", f"저장됨:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def export_history_each(self):
        """
        선택된 설비의 이력카드를 '개별 xlsx'로 만든 뒤,
        사용자가 지정한 경로에 'ZIP 한 파일'로 저장한다.
        (폴더 선택 → 개별 저장 방식 삭제, 저장 대화상자 하나로 고정)
        """
        if export_history_card_xlsx is None:
            QMessageBox.information(self, "안내", "이 기능은 아직 구성되지 않았습니다."); return

        codes = self._gather_checked_codes()
        if not codes:
            QMessageBox.information(self, "안내", "체크된 설비가 없습니다."); return

        start_dir = _start_dir()
        default_zip = os.path.join(start_dir, f"이력카드_개별_{len(codes)}대.zip")
        zip_path, _ = QFileDialog.getSaveFileName(
            self, "이력카드(개별) ZIP으로 저장", default_zip, "ZIP Archives (*.zip)"
        )
        if not zip_path:
            return
        # 확장자 보정
        if not os.path.splitext(zip_path)[1]:
            zip_path += ".zip"

        tmpdir = tempfile.mkdtemp(prefix="history_each_")
        ok, fail, errors = 0, 0, []

        base = self._base_date_value()
        try:
            # 1) 개별 파일 생성 (임시 폴더)
            for code in codes:
                try:
                    out_path = os.path.join(tmpdir, f"{code}_이력카드.xlsx")
                    export_history_card_xlsx(
                        code, path=out_path,
                        year_only=self.btn_toggle_year.isChecked(),
                        base_date=base,
                    )
                    ok += 1
                except Exception as e:
                    fail += 1
                    errors.append(f"{code}: {e}")

            if ok == 0:
                raise RuntimeError("생성된 이력카드 파일이 없습니다.")

            # 2) ZIP 생성
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for fn in os.listdir(tmpdir):
                    fp = os.path.join(tmpdir, fn)
                    if os.path.isfile(fp):
                        zf.write(fp, arcname=fn)

            if fail == 0:
                QMessageBox.information(self, "완료", f"{ok}건 ZIP 저장 완료\n파일: {zip_path}")
            else:
                msg = f"완료: {ok}건, 실패: {fail}건\nZIP: {zip_path}\n\n" + "\n".join(errors[:10])
                QMessageBox.warning(self, "일부 실패", msg)
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def _base_date_value(self) -> _date:
        qd = self.dt_base.date()
        return _date(qd.year(), qd.month(), qd.day())

    def _gather_checked_codes(self) -> List[str]:
        codes: List[str] = []
        for r in range(self.table.rowCount()):
            w = self.table.cellWidget(r, 0)
            if isinstance(w, QCheckBox) and w.isChecked():
                it = self.table.item(r, 1)
                code = it.text().strip() if it else ""
                if code:
                    codes.append(code)
        return codes

    def delete_selected(self):
        codes = self._gather_checked_codes()
        if not codes:
            c = self.current_code()
            if not c:
                QMessageBox.information(self, "안내", "먼저 설비를 선택하거나 체크하세요."); return
            codes = [c]

        lines = []
        total_rep = total_ph = total_acc = 0
        for code in codes:
            rep, ph, acc = get_delete_preview(code)
            lines.append(f"- {code}  (수리:{rep}, 사진:{ph}, 부속:{acc})")
            total_rep += rep; total_ph += ph; total_acc += acc
        detail = "\n".join(lines)

        box = QMessageBox(self)
        box.setWindowTitle("삭제 방법 선택")
        box.setText(f"선택한 설비 {len(codes)}건을 어떻게 처리할까요?")
        box.setInformativeText(
            "• 보관함 이동(권장): 화면에서 숨기고 DB에는 남겨둡니다.\n"
            "• 완전 삭제: 관련 이력/부속/사진까지 모두 지웁니다(되돌릴 수 없음)."
        )
        box.setDetailedText(f"[참조 요약]\n수리:{total_rep}  사진:{total_ph}  부속:{total_acc}\n\n개별 내역:\n{detail}")
        soft_btn = box.addButton("보관함 이동(안전)", QMessageBox.AcceptRole)
        hard_btn = box.addButton("완전 삭제", QMessageBox.DestructiveRole)
        box.addButton("취소", QMessageBox.RejectRole)
        box.exec()

        if box.clickedButton() not in (soft_btn, hard_btn):
            return
        mode = "soft" if box.clickedButton() is soft_btn else "hard"

        ok, fail, errs = 0, 0, []
        for code in codes:
            try:
                delete_equipment_by_code(code, mode=mode)
                ok += 1
            except Exception as e:
                fail += 1
                errs.append(f"{code}: {e}")

        self.refresh()
        if fail == 0:
            QMessageBox.information(self, "완료", f"{ok}건 {('보관함 이동' if mode=='soft' else '완전 삭제')} 완료")
        else:
            msg = f"완료: {ok}건, 실패: {fail}건\n\n" + "\n".join(errs[:10])
            QMessageBox.warning(self, "일부 실패", msg)

    def open_change_log(self):
        code = self.current_code()
        if not code:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        e = get_equipment_by_code(code)
        if not e or not getattr(e, "id", None):
            QMessageBox.warning(self, "오류", "설비를 찾을 수 없습니다.")
            return
        # ★ 코드도 함께 넘김 → 로그 테이블이 code/record_code 등을 쓸 때도 매칭
        dlg = ChangeLogDialog("equipment", int(e.id), self, record_code=code)
        dlg.exec()
