from __future__ import annotations
import os, shutil, time
from dataclasses import dataclass
from typing import List, Optional

import settings
from db import session_scope
from models import Photo

# ─────────────────────────────────────────────────────────
# 경로 설정: 서버 공유 폴더 기준
PHOTO_ROOT = settings.get_photo_root_dir()
TRASH_ROOT = settings.get_photo_trash_dir()

# 루트 보장(UNC는 권한 문제 시 생략 가능)
for p in (PHOTO_ROOT, TRASH_ROOT):
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass

def _safe_code(code: str) -> str:
    return "".join(ch for ch in (code or "") if ch.isalnum() or ch in "-_")

def _equip_dir(code: str) -> str:
    return os.path.join(PHOTO_ROOT, _safe_code(code))

def _trash_dir(code: str) -> str:
    return os.path.join(TRASH_ROOT, _safe_code(code))

def _ensure_dirs(code: str):
    for p in (_equip_dir(code), _trash_dir(code)):
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            pass

# ─────────────────────────────────────────────────────────
@dataclass
class PhotoInfo:
    filename: str
    path: str        # 절대경로(아이콘/미리보기용)
    size: int
    mtime: float
    in_trash: bool = False

def list_photos(equipment_code: str, include_trash: bool = False) -> List[PhotoInfo]:
    """설비 사진 목록(최신순). include_trash=True면 휴지통까지 같이."""
    code = _safe_code(equipment_code); _ensure_dirs(code)
    items: List[PhotoInfo] = []

    root = _equip_dir(code)
    try:
        for fn in sorted(os.listdir(root)):
            lp = os.path.join(root, fn)
            if os.path.isfile(lp) and fn.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif",".webp")):
                st = os.stat(lp); items.append(PhotoInfo(fn, lp, st.st_size, st.st_mtime, False))
    except Exception:
        pass
    items.sort(key=lambda x: x.mtime, reverse=True)

    if include_trash:
        troot = _trash_dir(code)
        try:
            for fn in sorted(os.listdir(troot)):
                lp = os.path.join(troot, fn)
                if os.path.isfile(lp):
                    st = os.stat(lp); items.append(PhotoInfo(fn, lp, st.st_size, st.st_mtime, True))
        except Exception:
            pass
    return items

def _unique_name(dst_dir: str, filename: str) -> str:
    name_root, ext = os.path.splitext(filename)
    dst = os.path.join(dst_dir, filename)
    i = 2
    while os.path.exists(dst):
        dst = os.path.join(dst_dir, f"{name_root}_{i}{ext}"); i += 1
    return dst

def add_photo(equipment_code: str, source_path: str) -> PhotoInfo:
    """
    외부 파일을 설비 폴더(서버)에 복사(이름 충돌 시 _2, _3...).
    DB에는 기록하지 않습니다(다중 사진 관리용). 대표사진 교체는 replace_main_photo() 사용.
    """
    code = _safe_code(equipment_code); _ensure_dirs(code)
    src = os.path.abspath(source_path)
    if not os.path.isfile(src):
        raise FileNotFoundError(source_path)
    dst_dir = _equip_dir(code)
    dst = _unique_name(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    st = os.stat(dst)
    return PhotoInfo(os.path.basename(dst), dst, st.st_size, st.st_mtime, False)

def delete_photo(equipment_code: str, filename: str, hard: bool=False) -> Optional[str]:
    """
    사진 삭제.
    - 기본: 휴지통으로 이동
    - hard=True: 완전 삭제(복구 불가)
    return: 최종 경로(휴지통 이동 경로) 또는 None
    """
    code = _safe_code(equipment_code); _ensure_dirs(code)
    src = os.path.join(_equip_dir(code), filename)
    if not os.path.exists(src):
        return None
    if hard:
        try: os.remove(src)
        except Exception: pass
        return None
    tdir = _trash_dir(code)
    try: os.makedirs(tdir, exist_ok=True)
    except Exception: pass
    name_root, ext = os.path.splitext(filename)
    dst = os.path.join(tdir, f"{name_root}_{int(time.time())}{ext}")
    try: shutil.move(src, dst)
    except Exception: return None
    return dst

def restore_photo(equipment_code: str, trash_filename: str) -> Optional[str]:
    """휴지통에서 복구."""
    code = _safe_code(equipment_code); _ensure_dirs(code)
    src = os.path.join(_trash_dir(code), trash_filename)
    if not os.path.exists(src): return None
    dst_dir = _equip_dir(code)
    dst = os.path.join(dst_dir, trash_filename)
    name_root, ext = os.path.splitext(trash_filename)
    i = 2
    while os.path.exists(dst):
        dst = os.path.join(dst_dir, f"{name_root}_{i}{ext}"); i += 1
    try: shutil.move(src, dst)
    except Exception: return None
    return dst

def open_folder(equipment_code: str):
    """파일 탐색기에서 설비 사진 폴더 열기(Windows)."""
    code = _safe_code(equipment_code); _ensure_dirs(code)
    path = _equip_dir(code)
    try:
        os.startfile(path)  # type: ignore[attr-defined]
    except Exception:
        pass

# ─────────────────────────────────────────────────────────
# 대표 사진 1장만 유지 + DB(Photo) 1건만 저장
def replace_main_photo(equipment_id: int, equipment_code: str, source_path: str) -> PhotoInfo:
    """
    - 서버 폴더로 복사
    - 설비 폴더의 기존 이미지 파일은 휴지통으로 이동
    - DB photo 레코드는 모두 지우고 1건만 상대경로로 재저장 (path, file_path 둘 다)
    """
    if not equipment_id or not equipment_code:
        raise ValueError("equipment_id / equipment_code 가 필요합니다.")
    code = _safe_code(equipment_code); _ensure_dirs(code)

    # 1) 기존 파일들 휴지통으로 이동
    for info in list_photos(code):
        try:
            delete_photo(code, info.filename, hard=False)
        except Exception:
            pass

    # 2) 새 파일 복사 (이름 충돌 방지)
    src = os.path.abspath(source_path)
    if not os.path.isfile(src):
        raise FileNotFoundError(source_path)
    dst_dir = _equip_dir(code)
    dst_abs = _unique_name(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst_abs)

    rel_path = os.path.join(code, os.path.basename(dst_abs))  # DB에는 상대경로 저장

    # 3) DB 반영
    with session_scope() as s:
        # 기존 레코드 삭제
        try:
            olds = s.query(Photo).filter(Photo.equipment_id == equipment_id).all()
            for p in olds: s.delete(p)
        except Exception:
            pass
        # 새 레코드 1건
        rec = Photo(
            equipment_id=equipment_id,
            equipment_code=code,
            path=rel_path,
            file_path=rel_path,
        )
        s.add(rec)

    st = os.stat(dst_abs)
    return PhotoInfo(os.path.basename(dst_abs), dst_abs, st.st_size, st.st_mtime, False)
