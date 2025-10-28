from __future__ import annotations
import os, json
from pathlib import Path
from typing import Dict, Any, List

# 설정 파일 경로
_SETTINGS_PATH = os.path.abspath("./app_settings.json")

# ─────────────────────────────────────────────
# 유틸: 데스크탑 경로
def _desktop_path() -> str:
    try:
        return str(Path.home() / "Desktop")
    except Exception:
        return os.path.abspath(".")

# ─────────────────────────────────────────────
# 기본값
_DEFAULTS: Dict[str, Any] = {
    # 저장 경로(내보내기 등)
    "default_save_dir": _desktop_path(),   # 기본 저장 폴더
    "last_save_dir": "",                   # 마지막 저장 폴더

    # 소모품 사유 프리셋
    "reason_presets": [
        "정기보충", "수리 사용", "라인전환", "불량폐기", "반납", "재고조정(+)", "재고조정(-)"
    ],
    "reason_favorites": ["수리 사용", "정기보충"],

    # ── DB 설정 ──
    "db_dir": r"\\192.168.2.4\new생산팀\생산기술파트\db",
    "db_file": "app.db",
    "db_url": "",  # 예) r"sqlite://///192.168.2.4/new생산팀/생산기술파트/db/app.db"

    # ── 사진 저장 루트(신규) ──
    # 서버 공유 폴더 아래 photos 디렉터리에 보관
    "photo_root_dir": r"\\192.168.2.4\new생산팀\생산기술파트\photos",
    # (선택) 휴지통 루트(비우면 photo_root_dir\_trash 사용)
    "photo_trash_dir": "",
}

# ─────────────────────────────────────────────
# 로드/세이브 공용 함수
def _load() -> Dict[str, Any]:
    if not os.path.isfile(_SETTINGS_PATH):
        return dict(_DEFAULTS)
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    out = dict(_DEFAULTS); out.update(data if isinstance(data, dict) else {})
    return out

def _save(data: Dict[str, Any]) -> None:
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ─────────────────────────────────────────────
# 저장 경로(내보내기 관련)
def get_default_save_dir() -> str:
    return _load().get("default_save_dir") or _desktop_path()

def set_default_save_dir(path: str) -> None:
    d = _load(); d["default_save_dir"] = path or _desktop_path(); _save(d)

def get_last_save_dir() -> str:
    return _load().get("last_save_dir") or ""

def update_last_save_dir(dirpath: str) -> None:
    if not dirpath: return
    d = _load(); d["last_save_dir"] = dirpath; _save(d)

def get_start_dir() -> str:
    return get_last_save_dir() or get_default_save_dir()

# ─────────────────────────────────────────────
# 사유 프리셋
def get_reason_presets() -> List[str]:
    d = _load(); presets = d.get("reason_presets") or []; favs = d.get("reason_favorites") or []
    return sorted(set(presets), key=lambda x: (0 if x in favs else 1, x))

def add_reason_preset(text: str, favorite: bool = False) -> None:
    text = (text or "").strip()
    if not text: return
    d = _load()
    pres = list(dict.fromkeys((d.get("reason_presets") or []) + [text]))
    d["reason_presets"] = pres
    if favorite:
        favs = set(d.get("reason_favorites") or []); favs.add(text)
        d["reason_favorites"] = sorted(favs)
    _save(d)

def get_reason_favorites() -> List[str]:
    return _load().get("reason_favorites") or []

def toggle_reason_favorite(text: str) -> None:
    text = (text or "").strip()
    if not text: return
    d = _load(); favs = set(d.get("reason_favorites") or [])
    if text in favs: favs.remove(text)
    else: favs.add(text)
    d["reason_favorites"] = sorted(favs); _save(d)

# ─────────────────────────────────────────────
# DB 설정
def get_db_dir() -> str:
    return _load().get("db_dir") or r"\\192.168.2.4\new생산팀\생산기술파트\db"

def set_db_dir(path: str) -> None:
    d = _load(); d["db_dir"] = path or r"\\192.168.2.4\new생산팀\생산기술파트\db"; _save(d)

def get_db_file() -> str:
    return _load().get("db_file") or "app.db"

def set_db_file(filename: str) -> None:
    d = _load(); d["db_file"] = filename or "app.db"; _save(d)

def get_db_url() -> str:
    return _load().get("db_url") or ""

def set_db_url(url: str) -> None:
    d = _load(); d["db_url"] = (url or "").strip(); _save(d)

def get_db_path() -> str:
    d = _load()
    dirp = d.get("db_dir") or r"\\192.168.2.4\new생산팀\생산기술파트\db"
    filep = d.get("db_file") or "app.db"
    return os.path.join(dirp, filep)

# ─────────────────────────────────────────────
# 사진 저장 설정(신규)
def get_photo_root_dir() -> str:
    return _load().get("photo_root_dir") or r"\\192.168.2.4\new생산팀\생산기술파트\photos"

def set_photo_root_dir(path: str) -> None:
    d = _load(); d["photo_root_dir"] = path or r"\\192.168.2.4\new생산팀\생산기술파트\photos"; _save(d)

def get_photo_trash_dir() -> str:
    d = _load()
    trash = d.get("photo_trash_dir") or ""
    if trash: return trash
    root = get_photo_root_dir()
    return os.path.join(root, "_trash")

def set_photo_trash_dir(path: str) -> None:
    d = _load(); d["photo_trash_dir"] = path or ""; _save(d)
