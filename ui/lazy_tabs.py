# ui/lazy_tabs.py
from __future__ import annotations
from typing import Callable, Dict, Optional
from PySide6.QtWidgets import QTabWidget, QWidget
from PySide6.QtCore import QObject

class LazyTabWidget(QTabWidget):
    """첫 클릭 때 팩토리로 위젯을 생성하는 탭 위젯"""
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._factories: Dict[int, Callable[[], QWidget]] = {}
        self._programmatic_build = False  # build_now()에서만 True
        self.currentChanged.connect(self._ensure_tab_built)

    def addLazyTab(self, factory: Callable[[], QWidget], title: str) -> int:
        placeholder = QWidget()  # 빈 자리만 넣어둠
        idx = self.addTab(placeholder, title)
        self._factories[idx] = factory
        return idx

    def _ensure_tab_built(self, index: int):
        if index in self._factories:
            factory = self._factories.pop(index)
            # removeTab 전에 기존 제목을 확보해야 안전
            old_title = self.tabText(index)
            real = factory()
            self.removeTab(index)
            self.insertTab(index, real, real.windowTitle() or old_title)
            # ⚠️ 코드에서 강제로 빌드(build_now)할 땐 포커스 바꾸지 않음
            if not self._programmatic_build:
                self.setCurrentIndex(index)

    # 코드에서 강제로 빌드하고 싶을 때:
    def build_now(self, index: int) -> QWidget:
        self._programmatic_build = True
        try:
            self._ensure_tab_built(index)
        finally:
            self._programmatic_build = False
        return self.widget(index)
