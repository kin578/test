from __future__ import annotations
from PySide6.QtWidgets import QLabel, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QGuiApplication, QImage, QKeySequence

class DroppableImageLabel(QLabel):
    """드래그&드롭 + Ctrl+V 붙여넣기 지원 라벨"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.on_drop_file = None    # callable(path: str)
        self.on_drop_image = None   # callable(img: QImage)

    def _is_image_file(self, path: str) -> bool:
        return path.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif",".webp"))

    def dragEnterEvent(self, e):
        md = e.mimeData()
        ok = False
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
            if isinstance(img, QPixmap): 
                img = img.toImage()
            if isinstance(img, QImage):
                self.on_drop_image(img)
                e.acceptProposedAction()
                return
        if md.hasUrls() and self.on_drop_file:
            for u in md.urls():
                if u.isLocalFile():
                    path = u.toLocalFile()
                    if self._is_image_file(path):
                        self.on_drop_file(path)
                        e.acceptProposedAction()
                        return
        e.ignore()

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Paste):
            cb = QGuiApplication.clipboard()
            md = cb.mimeData()
            img = cb.image()
            if not img.isNull() and self.on_drop_image:
                self.on_drop_image(img); return
            if md and md.hasUrls() and self.on_drop_file:
                for u in md.urls():
                    if u.isLocalFile():
                        path = u.toLocalFile()
                        if self._is_image_file(path):
                            self.on_drop_file(path); return
            QMessageBox.information(self, "안내", "클립보드에 이미지가 없습니다.")
        else:
            super().keyPressEvent(e)
