# pydracula_loader.py
from __future__ import annotations
import os
from PySide6.QtWidgets import QApplication

def apply_pydracula_full(app: QApplication,
                         base_dir: str = "vendor/pydracula",
                         qss_file: str = "themes/py_dracula_dark.qss") -> None:
    """
    PyDracula 풀셋(QSS + 리소스)을 적용.
    - base_dir 안에 modules/, widgets/, images/, resources.qrc 가 있어야 함
    - resources_rc.py는 미리 생성되어 있어야 함 (pyside6-rcc)
    """
    # 리소스 등록 (컴파일된 리소스가 있을 때만)
    try:
        import importlib.util
        res_path = os.path.join(base_dir, "modules", "resources_rc.py")
        if os.path.isfile(res_path):
            spec = importlib.util.spec_from_file_location("pydracula_resources", res_path)
            mod = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # 리소스 등록됨
    except Exception:
        # 없으면 패스(이미지 없는 QSS는 그대로 적용 가능)
        pass

    # QSS 적용
    qss_path = os.path.abspath(os.path.join(base_dir, qss_file))
    if not os.path.isfile(qss_path):
        raise FileNotFoundError(f"PyDracula QSS가 없습니다: {qss_path}")
    with open(qss_path, "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
