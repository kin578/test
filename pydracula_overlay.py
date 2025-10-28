from __future__ import annotations
from pathlib import Path
from typing import Optional, Union
from PySide6.QtWidgets import QApplication

# 오버레이 QSS 후보들
_DARK_OVERLAY_FILES = [
    "py_dracula_dark_overlay.qss",
    "vendor/pydracula/themes/py_dracula_dark_overlay.qss",
]

def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None

def apply_overlay(app: QApplication,
                  arg: Optional[Union[str, Path]] = None,
                  mode: Optional[str] = None) -> None:
    """
    두 가지 호출 방식을 모두 지원합니다.
      1) apply_overlay(app, \"경로.qss\")
      2) apply_overlay(app, mode=\"dark\")  # 경로 없이 모드만 넘어오는 경우

    어떤 방식이든 '드라큘라 다크 오버레이'만 적용합니다.
    """
    candidates: list[Path] = []
    if isinstance(arg, (str, Path)):
        candidates.append(Path(arg))
    else:
        candidates.extend(Path(p) for p in _DARK_OVERLAY_FILES)

    for p in candidates:
        if p.exists():
            qss = _read_text(p)
            if qss:
                # 기존 스타일 위에 덧씌우기
                app.setStyleSheet((app.styleSheet() or "") + "\n" + qss)
                return
    # 못 찾으면 조용히 패스
