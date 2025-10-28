# ui/tabs/history_tab.py
from __future__ import annotations
import os, tempfile
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QGuiApplication, QImage, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame, QSizePolicy,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QFileDialog, QMessageBox, QGroupBox, QScrollArea, QToolButton   # ★ QToolButton 추가
)

# 서비스/모델 (★ 네가 준 그대로 유지)
from services.equipment_service import get_equipment_by_code
from services.repair_service import list_repairs
from services.exporter import export_history_card_xlsx
from services.accessory_service import list_accessories  # 부속기구
from services.photo_service import list_photos, replace_main_photo, open_folder


# ─────────────────────────────────────────────────────────────
# 유틸 (네 코드 그대로)
def _fmt_kr_price(n) -> str:
    if n is None or n == "": 
        return ""
    try:
        return f"₩{float(n):,.0f}"
    except Exception:
        return str(n)

def _fmt_kr_date(y:int|None, m:int|None, d:int|None) -> str:
    if y:
        return f"{y}년 {m or 1}월 {d or 1}일"
    return ""


# ─────────────────────────────────────────────────────────────
# ★ 여기만 추가: 다크 QSS에서 사라지는 QFileDialog 툴버튼 보정
def _fix_file_dialog_toolbar(dlg: QFileDialog):
    """
    비네이티브 QFileDialog의 상단/우상단 툴버튼이 QSS 때문에 '보이는 것처럼 안 보일' 때
    텍스트 심볼을 강제로 넣어 가시성을 확보한다. (아이콘 상수 사용 안 함)
    """
    names = {
        "backButton": "←",
        "forwardButton": "→",
        "toParentButton": "↰",
        "newFolderButton": "+",
        "listModeButton": "≡",
        "detailModeButton": "▦",
    }
    for obj, text in names.items():
        btn: QToolButton = dlg.findChild(QToolButton, obj)
        if not btn:
            continue
        if not btn.text():
            btn.setText(text)
        # 너무 붙지 않게 살짝 여백
        btn.setStyleSheet("padding: 2px 6px;")

def _get_save_path_dark(parent: QWidget, title: str, suggest_path: str, filter_str: str) -> str:
    dlg = QFileDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setAcceptMode(QFileDialog.AcceptSave)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)  # 다크 유지
    dlg.setNameFilter(filter_str)
    if suggest_path:
        suggest_path = os.path.normpath(suggest_path)
        folder, name = os.path.split(suggest_path)
        if folder and os.path.isdir(folder):
            dlg.setDirectory(folder)
        if name:
            dlg.selectFile(name)
    _fix_file_dialog_toolbar(dlg)
    return dlg.selectedFiles()[0] if dlg.exec() and dlg.selectedFiles() else ""

def _get_open_path_dark(parent: QWidget, title: str, filter_str: str) -> str:
    dlg = QFileDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setAcceptMode(QFileDialog.AcceptOpen)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)  # 다크 유지
    dlg.setNameFilter(filter_str)
    _fix_file_dialog_toolbar(dlg)
    return dlg.selectedFiles()[0] if dlg.exec() and dlg.selectedFiles() else ""


# ─────────────────────────────────────────────────────────────
# 드래그/붙여넣기 이미지 라벨 (네 코드 유지)
class DroppableImageLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.on_drop_file = None   # callable(path: str)
        self.on_drop_image = None  # callable(img: QImage)

    def _is_image_file(self, path:str) -> bool:
        return path.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif",".webp"))

    def dragEnterEvent(self, e):
        md = e.mimeData(); ok = False
        if md.hasImage():
            ok = True
        elif md.hasUrls():
            for u in md.urls():
                if u.isLocalFile() and self._is_image_file(u.toLocalFile()):
                    ok = True; break
        if ok: e.acceptProposedAction()
        else: e.ignore()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasImage() and self.on_drop_image:
            img = md.imageData()
            if isinstance(img, QPixmap): img = img.toImage()
            if isinstance(img, QImage):
                self.on_drop_image(img); e.acceptProposedAction(); return
        if md.hasUrls() and self.on_drop_file:
            for u in md.urls():
                if u.isLocalFile():
                    path = u.toLocalFile()
                    if self._is_image_file(path):
                        self.on_drop_file(path); e.acceptProposedAction(); return
        e.ignore()

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Paste):
            cb = QGuiApplication.clipboard()
            img = cb.image()
            if not img.isNull() and self.on_drop_image:
                self.on_drop_image(img); return
            md = cb.mimeData()
            if md and md.hasUrls() and self.on_drop_file:
                for u in md.urls():
                    if u.isLocalFile() and self._is_image_file(u.toLocalFile()):
                        self.on_drop_file(u.toLocalFile()); return
            QMessageBox.information(self, "안내", "클립보드에 이미지가 없습니다.")
        else:
            super().keyPressEvent(e)


# ─────────────────────────────────────────────────────────────
class HistoryTab(QWidget):
    def __init__(self, on_open_repair=None):
        super().__init__()
        self.on_open_repair = on_open_repair  # (repair_id, equipment_id)
        root = QVBoxLayout(self)

        self.title = QLabel("이력카드: -")
        self.title.setStyleSheet("font-weight:600; font-size:16px;")
        root.addWidget(self.title)

        top = QHBoxLayout()
        root.addLayout(top)

        # 좌측 정보 패널 (네 구성 그대로)
        info = QGridLayout()
        info.setVerticalSpacing(6)
        info.setHorizontalSpacing(10)

        labels = [
            ("관리번호","code"),("설비명","name"),("모델명","model"),("설비크기","size"),
            ("전력용량","power"),("제조회사","maker"),("구입일자","in_date"),
            ("구입가격","price"),("설치장소","location"),("용도","purpose"),
            ("특이사항","note"),("Tel","tel")
        ]
        self.info_widgets: dict[str, QLabel|QTextEdit] = {}
        r = 0
        for lab, key in labels:
            labw = QLabel(lab)
            labw.setStyleSheet("font-weight:600;")
            if key == "note":
                wid = QTextEdit()
                wid.setReadOnly(True)
                wid.setMaximumHeight(70)
                wid.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
                wid.setStyleSheet("background: transparent; border: 1px solid palette(mid);"
                                  "border-radius: 6px; padding: 4px;")
            else:
                wid = QLabel("")
                wid.setFrameStyle(QFrame.StyledPanel | QFrame.Plain)
                wid.setStyleSheet("background: transparent; border: 1px solid palette(mid);"
                                  "border-radius: 6px; padding: 4px;")
            info.addWidget(labw, r, 0)
            info.addWidget(wid,  r, 1)
            self.info_widgets[key] = wid
            r += 1

        left = QWidget()
        left.setLayout(info)
        left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        top.addWidget(left, 6)

        # 우측 사진 + 버튼 (네 구성 그대로)
        right = QVBoxLayout()

        self.photo = DroppableImageLabel("사진 없음")
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setFixedSize(QSize(520, 360))
        self.photo.setStyleSheet("border:1px solid palette(mid); background: transparent;")
        self.photo.on_drop_file = self._save_replaced_image_from_file
        self.photo.on_drop_image = self._save_replaced_image_from_qimage
        right.addWidget(self.photo, alignment=Qt.AlignTop)

        btns = QHBoxLayout()
        self.btn_photo = QPushButton("사진 파일 선택")
        self.btn_paste = QPushButton("클립보드 붙여넣기")
        self.btn_photo_folder = QPushButton("사진 폴더 열기")
        self.btn_export_card = QPushButton("이력카드(엑셀) 내보내기")
        btns.addWidget(self.btn_photo)
        btns.addWidget(self.btn_paste)
        btns.addWidget(self.btn_photo_folder)
        btns.addWidget(self.btn_export_card)
        btns.addStretch()
        right.addLayout(btns)

        top.addLayout(right, 5)

        # 부속기구 (네 구성 그대로)
        acc_box = QVBoxLayout()
        acc_box.addWidget(QLabel("부속기구"))
        self.acc_table = QTableWidget(7, 4)
        self.acc_table.setHorizontalHeaderLabels(["No","품   명","규격","비고"])
        self.acc_table.verticalHeader().setVisible(False)
        self.acc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.acc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.acc_table.horizontalHeader().setStretchLastSection(True)
        for i in range(7):
            self.acc_table.setItem(i, 0, QTableWidgetItem(str(i+1)))
        acc_wrap = QWidget()
        acc_wrap.setLayout(acc_box)
        acc_box.addWidget(self.acc_table)
        root.addWidget(acc_wrap)

        # 이력 테이블 (네 구성 그대로)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["일자","구분","제목","내용","수리처","수리시간"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        root.addWidget(self.table)

        # 이벤트 (네 그대로)
        self.table.cellDoubleClicked.connect(self._open_repair_tab_from_history)
        self.btn_photo.clicked.connect(self.add_or_replace_photo_via_dialog)
        self.btn_paste.clicked.connect(self.paste_from_clipboard)
        self.btn_photo_folder.clicked.connect(self.open_photo_folder)
        self.btn_export_card.clicked.connect(self.export_card)

        self.current_equipment_id = None
        self.current_equipment_code = ""

    # ─────────────────────────────────────────────────────────
    # 내부 유틸 (네 로직 유지)
    def _load_photo(self, code:str):
        infos = list_photos(code, include_trash=False)
        path = infos[0].path if infos else None
        if path and os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                self.photo.setPixmap(
                    pm.scaled(self.photo.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                self.photo.setText("")
                return
        self.photo.setText("사진 없음")
        self.photo.setPixmap(QPixmap())

    def _set_info(self, key:str, value:str):
        w = self.info_widgets.get(key)
        if isinstance(w, QTextEdit):
            w.setPlainText(value or "")
        elif isinstance(w, QLabel):
            w.setText(value or "")

    # ─────────────────────────────────────────────────────────
    # 외부 API (네 로직 유지)
    def load_for_equipment(self, code:str):
        eq = get_equipment_by_code(code)
        if not eq:
            self.title.setText(f"이력카드: {code} (미등록)")
            self.table.setRowCount(0)
            return

        self.current_equipment_id = eq.id
        self.current_equipment_code = eq.code
        self.title.setText(f"이력카드: {eq.code} / {eq.name}")

        # 좌측 정보
        power = ""
        if eq.voltage and eq.power_kwh is not None:
            power = f"{eq.voltage}  {eq.power_kwh}kW"
        elif eq.voltage:
            power = eq.voltage
        elif eq.power_kwh is not None:
            power = f"{eq.power_kwh}kW"

        self._set_info("code", eq.code or "")
        self._set_info("name", eq.name or "")
        self._set_info("model", eq.model or "")
        self._set_info("size", eq.size_mm or "")
        self._set_info("power", power)
        self._set_info("maker", eq.maker or "")
        self._set_info("in_date", _fmt_kr_date(eq.in_year, eq.in_month, eq.in_day))
        self._set_info("price", _fmt_kr_price(eq.purchase_price))
        self._set_info("location", eq.location or "")
        self._set_info("purpose", (eq.purpose or ""))
        self._set_info("note", eq.note or "")
        self._set_info("tel", eq.maker_phone or "")

        # 사진
        self._load_photo(eq.code or "")

        # 부속기구
        for r in range(7):
            self.acc_table.setItem(r, 1, QTableWidgetItem(""))
            self.acc_table.setItem(r, 2, QTableWidgetItem(""))
            self.acc_table.setItem(r, 3, QTableWidgetItem(""))
        try:
            accs = list_accessories(eq.id)  # 각 항목: .name, .spec, .note
        except Exception:
            accs = []
        for idx, a in enumerate(accs[:7]):
            name = getattr(a, "name", "") or ""
            spec = getattr(a, "spec", "") or ""
            note = getattr(a, "note", "") or ""
            self.acc_table.setItem(idx, 1, QTableWidgetItem(name))
            self.acc_table.setItem(idx, 2, QTableWidgetItem(spec))
            self.acc_table.setItem(idx, 3, QTableWidgetItem(note))

        # 이력
        reps = list_repairs(equipment_id=eq.id)
        sort_on = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(reps))

        for i, r in enumerate(reps):
            def put(col, text, align=Qt.AlignLeft|Qt.AlignTop, store_id:bool=False):
                it = QTableWidgetItem("" if text is None else str(text))
                it.setTextAlignment(align)
                if store_id:
                    it.setData(Qt.UserRole, getattr(r, "id", None))
                self.table.setItem(i, col, it)

            put(0, getattr(r, "work_date", ""), Qt.AlignCenter, store_id=True)
            put(1, getattr(r, "kind", ""), Qt.AlignCenter)
            put(2, getattr(r, "title", ""), Qt.AlignLeft | Qt.AlignVCenter)
            put(3, getattr(r, "detail", ""))
            put(4, getattr(r, "vendor", "") or "", Qt.AlignCenter)
            put(5, getattr(r, "work_hours", "") or "", Qt.AlignCenter)

        self.table.setSortingEnabled(sort_on)

    def open_by_code(self, code: str):
        if not code:
            QMessageBox.information(self, "안내", "설비 코드가 비었습니다.")
            return
        self.load_for_equipment(code)

    def _open_repair_tab_from_history(self, row:int, col:int):
        it = self.table.item(row, 0)
        rid = it.data(Qt.UserRole) if it else None
        if rid and self.on_open_repair and self.current_equipment_id:
            try:
                self.on_open_repair(int(rid), int(self.current_equipment_id))
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────
    # 사진/엑셀 (네 로직 유지, 대화상자만 보정 함수로 교체)
    def _save_replaced_image_from_file(self, src_path:str):
        if not (self.current_equipment_id and self.current_equipment_code):
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        try:
            replace_main_photo(self.current_equipment_id, self.current_equipment_code, src_path)
            self._load_photo(self.current_equipment_code)
            QMessageBox.information(self, "완료", "사진이 교체되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _save_replaced_image_from_qimage(self, img: QImage):
        if not (self.current_equipment_id and self.current_equipment_code):
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        if img.isNull():
            QMessageBox.information(self, "안내", "이미지 데이터가 비었습니다.")
            return
        try:
            tmp = os.path.join(tempfile.gettempdir(), f"IMG_{int(datetime.now().timestamp()*1000)}.png")
            img.save(tmp, "PNG")
            self._save_replaced_image_from_file(tmp)
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def add_or_replace_photo_via_dialog(self):
        if not self.current_equipment_id:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        # ★ 비네이티브 + 우상단 버튼 텍스트 보정
        path = _get_open_path_dark(self, "사진 선택(한 장만 사용됩니다)", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not path:
            return
        self._save_replaced_image_from_file(path)

    def paste_from_clipboard(self):
        cb = QGuiApplication.clipboard()
        img = cb.image()
        if not img.isNull():
            self._save_replaced_image_from_qimage(img)
            return
        md = cb.mimeData()
        if md and md.hasUrls():
            for u in md.urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith(
                    (".png",".jpg",".jpeg",".bmp",".gif",".webp")
                ):
                    self._save_replaced_image_from_file(u.toLocalFile()); return
        QMessageBox.information(self, "안내", "클립보드에 이미지가 없습니다.")

    def export_card(self):
        if not self.current_equipment_code:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        # ★ 비네이티브 + 우상단 버튼 텍스트 보정
        suggest = f"{self.current_equipment_code}_이력카드.xlsx"
        path = _get_save_path_dark(self, "이력카드 저장", suggest, "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            p = export_history_card_xlsx(self.current_equipment_code, path=path)
            QMessageBox.information(self, "완료", f"저장됨:\n{p}")
        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def open_photo_folder(self):
        if not self.current_equipment_code:
            QMessageBox.information(self, "안내", "먼저 설비를 선택하세요.")
            return
        try:
            open_folder(self.current_equipment_code)
        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))
