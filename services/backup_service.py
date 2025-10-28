from __future__ import annotations
import os
import sys
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

from sqlalchemy import text

# DB 세션 (현재 연결된 DB의 실제 물리 경로를 PRAGMA로 조회하기 위해)
from db import session_scope

# settings 가 있다면 사진 루트/시작 폴더를 그대로 사용
try:
    import settings
    _PHOTO_ROOT = settings.get_photo_root_dir()  # 서버/로컬 어떤 경로든 OK
except Exception:
    _PHOTO_ROOT = None


# ─────────────────────────────────────────────────────────
# 경로 유틸
def _app_root() -> str:
    """
    실행 환경 별 앱 루트 폴더:
      - PyInstaller(onendir): exe가 있는 폴더
      - 개발 실행: 프로젝트 루트(services/.. 기준 상위)
    """
    if getattr(sys, "frozen", False):  # PyInstaller로 빌드된 exe
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _backups_dir() -> str:
    d = os.path.join(_app_root(), "backups")
    os.makedirs(d, exist_ok=True)
    return d

def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _default_zip_path(note: str = "") -> str:
    note = f"_{note}" if note else ""
    return os.path.join(_backups_dir(), f"backup_{_timestamp()}{note}.zip")


# ─────────────────────────────────────────────────────────
# 현재 사용 중인 SQLite 파일 경로 찾기 (서버 UNC/로컬 모두 지원)
def _sqlite_main_db_path() -> Optional[str]:
    """
    현재 연결된 SQLite 'main' DB의 물리 파일 경로를 PRAGMA로 조회.
    서버 UNC(\\srv\share\...app.db)로 연결되어 있어도 정확히 반환됨.
    """
    try:
        with session_scope() as s:
            rows = s.execute(text("PRAGMA database_list;")).all()
        # rows: (seq, name, file)
        for row in rows:
            name = row[1] if isinstance(row, (tuple, list)) else getattr(row, "name", None)
            file_ = row[2] if isinstance(row, (tuple, list)) else getattr(row, "file", None)
            if str(name).lower() == "main" and file_:
                return file_
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────
# ZIP 내부에 안내문(README.txt) 넣기
def _write_readme(zf: zipfile.ZipFile, included: List[Tuple[str, str]], include_photos: bool):
    lines = [
        "Equipment Manager Backup",
        f"Created: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "Included items:",
    ]
    if included:
        for src, arc in included:
            lines.append(f" - {arc}  (from: {src})")
    else:
        lines.append(" - [EMPTY] No files were detected.")
        lines.append("   * Possible reasons:")
        lines.append("     - Database path could not be detected (PRAGMA failed).")
        lines.append("     - The database file does not exist or is in-memory.")
        lines.append("     - Access permission issue on the DB server path.")

    lines += [
        "",
        f"[Photos included] : {'YES' if include_photos else 'NO'}",
        "  (Photos are usually large. We exclude them by default.)",
    ]
    zf.writestr("README.txt", ("\n".join(lines) + "\n").encode("utf-8"))


# ─────────────────────────────────────────────────────────
# 백업 타깃 수집
def _collect_backup_targets(include_photos: bool) -> List[Tuple[str, str]]:
    """
    반환: [(소스경로, ZIP내 경로)]
    - DB: 항상 시도(찾히면 포함)
    - app_settings.json: 있으면 포함
    - photos: include_photos=True 일 때만 포함(용량 큼)
    """
    targets: List[Tuple[str, str]] = []

    # 1) DB (현재 연결된 실제 파일)
    db_path = _sqlite_main_db_path()
    if db_path and os.path.isfile(db_path):
        # ZIP 내에는 'db/파일명.db' 로 넣음 (예전 'data/app.db' 호환이 아님)
        targets.append((db_path, os.path.join("db", os.path.basename(db_path))))

    # 2) 앱 설정
    app_settings = os.path.join(_app_root(), "app_settings.json")
    if os.path.isfile(app_settings):
        targets.append((app_settings, os.path.join("config", "app_settings.json")))

    # 3) 사진(선택)
    if include_photos:
        photo_root = _PHOTO_ROOT or os.path.join(_app_root(), "photos")
        if os.path.isdir(photo_root):
            # 루트 아래 전체 파일을 그대로 photos/ 이하로 넣음
            base = Path(photo_root)
            for p in base.rglob("*"):
                if p.is_file():
                    arc = os.path.join("photos", str(p.relative_to(base)).replace("\\", "/"))
                    targets.append((str(p), arc))

    return targets


# ─────────────────────────────────────────────────────────
# 공개 API: 백업 만들기
def make_backup(extra_note: str = "", include_photos: bool = False) -> str:
    """
    ZIP 백업 생성 후 경로 반환.
      - 기본 포함: DB(현재 연결된 실제 파일), app_settings.json(있으면)
      - 사진: 기본 미포함 (include_photos=True로 켜면 photos 루트 전체 포함)
    """
    zip_path = _default_zip_path(extra_note)
    targets = _collect_backup_targets(include_photos)

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in targets:
            try:
                zf.write(src, arcname=arc)
            except Exception:
                # 개별 항목 실패는 무시(README에서 전체 안내)
                pass
        _write_readme(zf, targets, include_photos)

    return zip_path

# 호환 별칭(원하면 다른 이름으로도 호출 가능)
create_backup = make_backup


# ─────────────────────────────────────────────────────────
# ZIP 미리보기(간단 유효성)
def _extract_preview(zip_path: str) -> Tuple[bool, str]:
    if not os.path.isfile(zip_path):
        return False, "파일이 존재하지 않습니다."
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            has_db = any(n.startswith("db/") and n.lower().endswith(".db") for n in names) \
                     or any(n.endswith("data/app.db") for n in names)  # 구버전 호환
            has_photos = any(n.startswith("photos/") for n in names)
            return True, f"- 포함 항목:\n  · DB: {'예' if has_db else '없음'}\n  · photos 폴더: {'예' if has_photos else '없음'}\n  · 파일 수: {len(names)}"
    except Exception as e:
        return False, f"ZIP 확인 실패: {e}"


# ─────────────────────────────────────────────────────────
# 복구
def restore_from_zip(zip_path: str, overwrite_photos: bool = False) -> str:
    """
    ZIP → 현재 사용 DB/사진으로 복구.
      - DB: 현재 연결된 DB 실제 경로를 PRAGMA로 찾아 그 파일을 교체
      - photos: ZIP에 들어있으면 사진 루트로 복구(기본 덮어쓰기 안 함)
      - 기존 파일은 backups/prev_타임스탬프/ 에 보관
    return: prev 백업 폴더 경로
    """
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(zip_path)

    prev_dir = os.path.join(_backups_dir(), f"prev_{_timestamp()}")
    os.makedirs(prev_dir, exist_ok=True)

    # 1) 현재 DB 경로 파악 & 기존 파일 보관
    current_db = _sqlite_main_db_path()
    if current_db and os.path.isfile(current_db):
        shutil.copy2(current_db, os.path.join(prev_dir, os.path.basename(current_db)))

    # 2) 사진 루트 파악 & 보관(zip)
    photo_root = _PHOTO_ROOT or os.path.join(_app_root(), "photos")
    if os.path.isdir(photo_root):
        shutil.make_archive(os.path.join(prev_dir, "photos"), "zip", photo_root)

    # 3) ZIP에서 DB/사진 꺼내기
    with zipfile.ZipFile(zip_path, "r") as z:
        # (a) DB 복구
        # 우선순위: db/*.db → (구버전) data/app.db
        db_members = [n for n in z.namelist() if n.startswith("db/") and n.lower().endswith(".db")]
        legacy_member = "data/app.db" if "data/app.db" in z.namelist() else None

        if current_db:
            # target 폴더 생성
            os.makedirs(os.path.dirname(current_db), exist_ok=True)
            if db_members:
                # 첫 번째 DB 파일을 현재 경로로 추출
                tmp_dir = os.path.join(prev_dir, "_tmp_db_extract")
                os.makedirs(tmp_dir, exist_ok=True)
                z.extract(db_members[0], path=tmp_dir)
                src_file = os.path.join(tmp_dir, db_members[0])
                shutil.copy2(src_file, current_db)
                shutil.rmtree(tmp_dir, ignore_errors=True)
            elif legacy_member:
                tmp_dir = os.path.join(prev_dir, "_tmp_db_extract")
                os.makedirs(tmp_dir, exist_ok=True)
                z.extract(legacy_member, path=tmp_dir)
                src_file = os.path.join(tmp_dir, legacy_member)
                shutil.copy2(src_file, current_db)
                shutil.rmtree(tmp_dir, ignore_errors=True)
            # else: ZIP에 DB가 없을 수도 있음(README 참고)

        # (b) photos 복구
        photo_members = [n for n in z.namelist() if n.startswith("photos/")]
        if photo_members:
            # 덮어쓰기 옵션
            if overwrite_photos and os.path.isdir(photo_root):
                shutil.rmtree(photo_root, ignore_errors=True)
            os.makedirs(photo_root, exist_ok=True)
            # 선택 멤버만 추출
            for m in photo_members:
                # m 은 항상 photos/ 로 시작
                target = os.path.join(photo_root, m.replace("photos/", "", 1))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(m) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    return prev_dir


# ─────────────────────────────────────────────────────────
# UI Helper (MainWindow 등에서 사용)
def backup_wizard(parent=None) -> str:
    """
    간단 백업(즉시 ZIP) – 사진은 기본 미포함:
    사진까지 포함하려면 UI에서 make_backup(include_photos=True)로 호출하도록 바꿔도 됨.
    """
    return make_backup(include_photos=False)

def restore_wizard(parent=None) -> Optional[str]:
    """
    파일 선택 → 미리보기 → 복구 실행
    - DB는 '현재 앱이 붙어있는 DB 파일'로 복구됨(서버/로컬 자동)
    - 사진은 ZIP에 있을 때만 복구(기본 덮어쓰기 안 함)
    """
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    path, _ = QFileDialog.getOpenFileName(parent, "복구 ZIP 선택", _backups_dir(), "ZIP Files (*.zip)")
    if not path:
        return None
    ok, info = _extract_preview(path)
    if not ok:
        QMessageBox.critical(parent, "오류", info); return None
    if QMessageBox.question(parent, "복구 확인", f"{os.path.basename(path)}\n\n{info}\n\n복구할까요?") != QMessageBox.Yes:
        return None
    prev = restore_from_zip(path, overwrite_photos=False)
    QMessageBox.information(parent, "완료", f"복구 완료\n이전 데이터는 보관됨:\n{prev}")
    return prev


# ─────────────────────────────────────────────────────────
# CLI 테스트(원하면 터미널에서 실행)
if __name__ == "__main__":
    out = make_backup()
    print(f"Backup created: {out}")
