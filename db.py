from __future__ import annotations
import os
import sqlite3
import importlib
from contextlib import contextmanager
from typing import Generator, Tuple

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# ─────────────────────────────────────────────────────────────
# settings 로드 (함수형/속성형 둘 다 지원)
try:
    import settings  # get_db_url(), get_db_dir(), get_db_file() 또는 DB_URL/DB_DIR/DB_FILE
except Exception:
    settings = None


def _get_from_settings(name: str, default: str | None = None) -> str | None:
    """
    settings에서 값을 가져온다.
    - get_{name} 함수가 있으면 그걸 호출
    - 없으면 NAME(대문자) 속성을 사용
    """
    if not settings:
        return default
    func_name = f"get_{name.lower()}"
    if hasattr(settings, func_name):
        try:
            return getattr(settings, func_name)() or default
        except Exception:
            return default
    attr_name = name.upper()
    return getattr(settings, attr_name, default)


# ─────────────────────────────────────────────────────────────
# 경로/URL 유틸
def _is_unc_path(p: str) -> bool:
    # \\server\share\... 또는 //server/share/...
    return p.startswith("\\\\") or p.startswith("//")


def _is_unc_url(url: str) -> bool:
    # SQLite UNC URL은 보통 'sqlite://///server/share/...' (슬래시 5개로 시작)
    return url.startswith("sqlite://///")


def _sqlite_url_from_path(path: str) -> str:
    r"""
    모든 OS/경로(특히 UNC)를 SQLAlchemy SQLite URL로 변환.
    """
    abspath = os.path.abspath(path)

    # UNC 처리
    if _is_unc_path(abspath):
        forward = abspath.replace("\\", "/")
        if forward.startswith("//"):
            forward = forward[2:]  # 'server/share/...' 로
        return f"sqlite://///{forward}"

    # 로컬 경로: 슬래시 통일
    forward = abspath.replace("\\", "/")
    if forward.startswith("/"):
        return f"sqlite:///{forward}"
    return f"sqlite:///{forward}"


def _get_db_dir_and_file() -> Tuple[str, str]:
    """
    DB 저장 폴더/파일명 결정
    우선순위:
    1) settings (get_db_dir/get_db_file or DB_DIR/DB_FILE)
    2) 환경변수 (DB_DIR/DB_FILE)
    3) 기본값: ./data/app.db
    """
    default_dir = os.path.join(os.path.dirname(__file__), "data")
    default_file = "app.db"

    d = _get_from_settings("db_dir")
    f = _get_from_settings("db_file")

    d = d or os.environ.get("DB_DIR")
    f = f or os.environ.get("DB_FILE")

    d = d or default_dir
    f = f or default_file

    return d, f


# ─────────────────────────────────────────────────────────────
# DB URL 최종 결정
DB_URL: str | None = None

# 1) settings의 db_url이 있으면 최우선
cfg_url = _get_from_settings("db_url", "")
if cfg_url:
    DB_URL = cfg_url.strip()

DB_DIR, DB_FILE = _get_db_dir_and_file()
DB_PATH = os.path.join(DB_DIR, DB_FILE)

# 2) db_url이 비어 있으면 db_dir+db_file 조합으로 URL 생성
if not DB_URL:
    try:
        # 로컬일 땐 폴더 생성, UNC는 권한/존재 가정
        if not _is_unc_path(DB_DIR):
            os.makedirs(DB_DIR, exist_ok=True)
    except Exception:
        pass
    DB_URL = _sqlite_url_from_path(DB_PATH)


# ─────────────────────────────────────────────────────────────
# SQLAlchemy 엔진/세션/베이스
class Base(DeclarativeBase):
    pass


engine = create_engine(
    DB_URL,
    future=True,
    pool_pre_ping=True,
    # GUI(스레드) 환경에서 SQLite는 check_same_thread=False가 안정적
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)

# ★ 커밋 후 객체 만료 방지 → DetachedInstanceError 예방!
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,   # ← 이 한 줄이 핵심
)


# SQLite PRAGMA: 외래키 ON, 저널 모드(UNC=DELETE, Local=WAL)
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _record):
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON;")
        # UNC(네트워크 공유)에서는 WAL 비권장 → DELETE 모드
        use_delete = False
        try:
            if DB_URL.startswith("sqlite") and (_is_unc_path(DB_PATH) or _is_unc_url(DB_URL)):
                use_delete = True
        except Exception:
            pass
        journal = "DELETE" if use_delete else "WAL"
        try:
            cur.execute(f"PRAGMA journal_mode={journal};")
        except Exception:
            pass
    finally:
        try:
            cur.close()
        except Exception:
            pass


@contextmanager
def session_scope() -> Generator:
    """with session_scope() as s: ...  패턴용 세션 컨텍스트"""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ─────────────────────────────────────────────────────────────
# 스키마 보강(증분 마이그레이션)
def _table_exists(conn, table: str) -> bool:
    q = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table})
    return q.scalar() is not None


def _col_exists(conn, table: str, col: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    # (cid, name, type, notnull, dflt_value, pk)
    return any(r[1] == col for r in rows)


def _ensure_equipment_columns(conn):
    if not _table_exists(conn, "equipment"):
        return
    for col, ddl in [
        ("status",     "ALTER TABLE equipment ADD COLUMN status TEXT"),
        ("category",   "ALTER TABLE equipment ADD COLUMN category TEXT"),
        ("is_deleted", "ALTER TABLE equipment ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"),
        ("deleted_at", "ALTER TABLE equipment ADD COLUMN deleted_at TEXT"),
        ("created_at", "ALTER TABLE equipment ADD COLUMN created_at TEXT"),
        # ★ 새로 추가: 용도(purpose) 분리
        ("purpose",    "ALTER TABLE equipment ADD COLUMN purpose VARCHAR(200)"),
    ]:
        try:
            if not _col_exists(conn, "equipment", col):
                conn.execute(text(ddl))
        except Exception:
            pass


def _ensure_consumable_txn_columns(conn):
    if not _table_exists(conn, "consumable_txn"):
        return
    try:
        if not _col_exists(conn, "consumable_txn", "created_at"):
            conn.execute(text("ALTER TABLE consumable_txn ADD COLUMN created_at TEXT"))
    except Exception:
        pass
    try:
        if not _col_exists(conn, "consumable_txn", "txn_time"):
            conn.execute(
                text(
                    "ALTER TABLE consumable_txn "
                    "ADD COLUMN txn_time TEXT NOT NULL DEFAULT (datetime('now'))"
                )
            )
    except Exception:
        pass


def _ensure_consumable_columns(conn):
    if not _table_exists(conn, "consumable"):
        return
    try:
        if not _col_exists(conn, "consumable", "note"):
            conn.execute(text("ALTER TABLE consumable ADD COLUMN note TEXT"))
    except Exception:
        pass


def ensure_db():
    """
    - 모델 로드(메타데이터 등록)
    - 테이블 생성
    - 누락 컬럼 보강(증분 마이그레이션)
    """
    importlib.import_module("models")  # 메타데이터에 모델 등록

    # 테이블 생성
    Base.metadata.create_all(bind=engine)

    # 증분 마이그레이션
    with engine.begin() as conn:
        _ensure_equipment_columns(conn)
        _ensure_consumable_txn_columns(conn)
        _ensure_consumable_columns(conn)
