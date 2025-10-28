from __future__ import annotations
import os
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QFileDialog, QMessageBox, QLabel
)
from services.photo_service import list_photos, add_photo, delete_photo, restore_photo, open_folder

class PhotoManager(QWidget):
    """
    간단한 사진 관리자
    - 추가, 삭제(휴지통 이동), 복구, 폴더 열기, 새로고침
    """
    def __init__(self, equipment_code: str, parent=None):
        super().__init__(parent)
        self.equipment_code = equipment_code
        self.setWindowTitle(f"사진 관리 - {equipment_code}")
        self.resize(800, 560)

        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(160, 120))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setSpacing(8)
        self.list.setMovement(QListWidget.Static)
        self.list.setSelectionMode(self.list.ExtendedSelection)

        btn_add = QPushButton("추가")
        btn_del = QPushButton("삭제(휴지통)")
        btn_restore = QPushButton("복구(휴지통→원복)")
        btn_folder = QPushButton("폴더 열기")
        btn_refresh = QPushButton("새로고침")

        btn_add.clicked.connect(self.on_add)
        btn_del.clicked.connect(self.on_delete)
        btn_restore.clicked.connect(self.on_restore)
        btn_folder.clicked.connect(self.on_open_folder)
        btn_refresh.clicked.connect(self.refresh)

        top = QHBoxLayout()
        top.addWidget(QLabel(f"설비번호: {equipment_code}"))
        top.addStretch()

        bar = QHBoxLayout()
        for b in (btn_add, btn_del, btn_restore, btn_folder, btn_refresh):
            bar.addWidget(b)
        bar.addStretch()

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.list)
        lay.addLayout(bar)

        self.refresh()

    def refresh(self):
        self.list.clear()
        for info in list_photos(self.equipment_code, include_trash=True):
            item = QListWidgetItem(QIcon(info.path), f"{'[휴지통] ' if info.in_trash else ''}{info.filename}")
            item.setData(Qt.UserRole, info)
            self.list.addItem(item)

    def on_add(self):
        files, _ = QFileDialog.getOpenFileNames(self, "사진 추가", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)")
        if not files: return
        ok = 0
        for path in files:
            try:
                add_photo(self.equipment_code, path)
                ok += 1
            except Exception as e:
                QMessageBox.warning(self, "추가 실패", f"{os.path.basename(path)}\n{e}")
        if ok:
            self.refresh()

    def _selected(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count()) if self.list.item(i).isSelected()]

    def on_delete(self):
        sel = self._selected()
        if not sel:
            QMessageBox.information(self, "안내", "삭제할 사진을 선택해주세요.")
            return
        n=0
        for info in sel:
            if info.in_trash:
                continue
            try:
                delete_photo(self.equipment_code, info.filename, hard=False)
                n += 1
            except Exception as e:
                QMessageBox.warning(self, "삭제 실패", f"{info.filename}\n{e}")
        if n:
            self.refresh()

    def on_restore(self):
        sel = self._selected()
        if not sel:
            QMessageBox.information(self, "안내", "복구할 사진을 선택해주세요.")
            return
        n=0
        for info in sel:
            if not info.in_trash:
                continue
            try:
                restore_photo(self.equipment_code, info.filename)
                n += 1
            except Exception as e:
                QMessageBox.warning(self, "복구 실패", f"{info.filename}\n{e}")
        if n:
            self.refresh()

    def on_open_folder(self):
        open_folder(self.equipment_code)
