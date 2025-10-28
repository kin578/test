# ui/dialog_utils.py
from __future__ import annotations
import os
import sys
import threading
import time
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QWidget

# ─────────────────────────────────────────────
# 현재 환경이 Windows 인지 간단 체크
def _is_windows() -> bool:
    return sys.platform.startswith("win")

# 우리 커스텀 파일 대화상자 패치(프레임리스)가 활성화되어 있는지 감지
# - enable_file_dialog_fix(True)가 적용되면 QFileDialog.getSaveFileName 등의
#   정적 메서드가 ui.file_dialog_patch 모듈의 함수로 바뀜.
def _using_custom_frameless_dialogs() -> bool:
    mod_names = (
        getattr(QFileDialog.getOpenFileName,  "__module__", ""),
        getattr(QFileDialog.getOpenFileNames, "__module__", ""),
        getattr(QFileDialog.getSaveFileName, "__module__", ""),
        getattr(QFileDialog.getExistingDirectory, "__module__", ""),
    )
    return any("ui.file_dialog_patch" in m for m in mod_names)

# ─────────────────────────────────────────────
# Windows 전용: 네이티브 파일 대화상자에 '다크 타이틀바' 적용
#  - 내용은 100% 네이티브 그대로(아이콘, 리스트, 트리 모두 OS 기본 UI)
#  - 제목 표시줄/틀만 어두운 톤으로 전환
#  - Windows 10(1809+) / 11에서만 효과, 다른 OS 또는 커스텀 파일창에서는 자동 무시
if _is_windows():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

    EnumWindows = user32.EnumWindows
    EnumWindows.argtypes = [ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    EnumWindows.restype = wintypes.BOOL

    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    GetWindowThreadProcessId.restype = wintypes.DWORD

    IsWindowVisible = user32.IsWindowVisible
    IsWindowVisible.argtypes = [wintypes.HWND]
    IsWindowVisible.restype = wintypes.BOOL

    GetClassNameW = user32.GetClassNameW
    GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    GetClassNameW.restype = ctypes.c_int

    DwmSetWindowAttribute = dwmapi.DwmSetWindowAttribute
    DwmSetWindowAttribute.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    DwmSetWindowAttribute.restype = wintypes.HRESULT

    # Windows 10 1809: 19, Windows 10 1903+: 20
    DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20

    _THIS_PID = os.getpid()

    def _try_set_dark_titlebar(hwnd: int) -> bool:
        """해당 윈도우 핸들에 다크 타이틀바 속성 적용(가능한 버전에서만). 실패해도 조용히 무시."""
        value = ctypes.c_int(1)
        for attr in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            hr = DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value))
            if hr == 0:
                return True
        return False

    def _owned_by_this_process(hwnd: int) -> bool:
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == _THIS_PID

    def _looks_like_file_dialog(hwnd: int) -> bool:
        """파일 대화상자로 보이는 네이티브 창만 선별(클래스명 기준)."""
        if not IsWindowVisible(hwnd):
            return False
        buf = ctypes.create_unicode_buffer(256)
        GetClassNameW(hwnd, buf, 256)
        cls = buf.value or ""
        # 대표적인 공용 대화상자 클래스들
        return cls in ("#32770", "OperationStatusWindow", "ExploreWClass", "CabinetWClass")

    def _poll_and_dark_titlebar(stop_evt: threading.Event, timeout_sec: float = 5.0):
        """
        짧은 시간 동안 현재 프로세스가 소유한 최상위 창을 훑으며
        '파일 대화상자'로 보이는 윈도우에 다크 타이틀바 적용.
        """
        import time as _time
        start = _time.time()
        CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def _enum_proc(hwnd, lparam):
            try:
                if _owned_by_this_process(hwnd) and _looks_like_file_dialog(hwnd):
                    _try_set_dark_titlebar(hwnd)
            except Exception:
                pass
            return True

        cb = CALLBACK(_enum_proc)
        while not stop_evt.is_set() and (_time.time() - start) < timeout_sec:
            try:
                EnumWindows(cb, 0)
            except Exception:
                pass
            _time.sleep(0.05)

    class _DarkTitlebarContext:
        """
        네이티브 파일 대화상자 앞뒤로만 잠깐 백그라운드 스캔해 다크 타이틀바 적용.
        커스텀(프레임리스) 파일창 사용 중이면 자동으로 아무 것도 하지 않음.
        """
        def __init__(self):
            self._stop = threading.Event()
            self._th: Optional[threading.Thread] = None

        def __enter__(self):
            # 커스텀 파일창이 활성화된 경우엔 스레드 자체를 띄우지 않음
            if _using_custom_frameless_dialogs():
                return self
            self._th = threading.Thread(target=_poll_and_dark_titlebar, args=(self._stop,), daemon=True)
            self._th.start()
            return self

        def __exit__(self, exc_type, exc, tb):
            self._stop.set()
            if self._th and self._th.is_alive():
                self._th.join(timeout=0.2)
            return False
else:
    class _DarkTitlebarContext:
        """윈도우가 아니면 아무 것도 하지 않는 더미 컨텍스트."""
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False

# ─────────────────────────────────────────────
# 공개 API (기존 시그니처 유지)
# 주의: enable_file_dialog_fix(True)로 커스텀 파일창이 켜져 있으면
#       아래 함수들은 자동으로 '커스텀 파일창'을 사용한다(우리가 패치한 정적 메서드가 호출됨).
#       네이티브 파일창을 강제하려면 enable_file_dialog_fix(False)로 원복 후 호출하면 된다.

def get_open_path(parent: QWidget, title: str, start_dir: str, filter_str: str = "All Files (*.*)") -> str:
    """
    파일 열기
    - 커스텀 파일창이 켜져 있으면: 프레임리스/테마 적용된 커스텀 창 사용
    - 네이티브 파일창이면: Windows에서 다크 타이틀바 자동 적용 시도
    """
    with _DarkTitlebarContext():
        path, _ = QFileDialog.getOpenFileName(parent, title, start_dir, filter_str)
    return path or ""

def get_save_path(parent: QWidget, title: str, default_path: str, filter_str: str = "All Files (*.*)") -> str:
    """
    파일 저장
    - 커스텀 파일창이 켜져 있으면: 프레임리스/테마 적용된 커스텀 창 사용
    - 네이티브 파일창이면: Windows에서 다크 타이틀바 자동 적용 시도
    """
    with _DarkTitlebarContext():
        path, _ = QFileDialog.getSaveFileName(parent, title, default_path, filter_str)
    return path or ""

def get_dir_path(parent: QWidget, title: str, start_dir: str) -> str:
    """
    폴더 선택
    - 커스텀 파일창이 켜져 있으면: 프레임리스/테마 적용된 커스텀 창 사용
    - 네이티브 파일창이면: Windows에서 다크 타이틀바 자동 적용 시도
    """
    with _DarkTitlebarContext():
        path = QFileDialog.getExistingDirectory(parent, title, start_dir)
    return path or ""
