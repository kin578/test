from __future__ import annotations
import os, json, hashlib, secrets
from datetime import datetime, date, datetime as _dt
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Table, Column, Integer, String, Boolean, DateTime, MetaData,
    select, insert, update, delete, func
)
from sqlalchemy.exc import IntegrityError

from db import session_scope

# ─────────────────────────────────────────
# DB 테이블(코어) 정의: ORM Base에 의존하지 않음
_METADATA = MetaData()
USERS = Table(
    "users", _METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(100), unique=True, nullable=False),     # 로그인 ID
    Column("role", String(30), nullable=False, default="user"),   # admin/user/viewer
    Column("email", String(200)),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("salt", String(64), nullable=False),
    Column("pw_hash", String(128), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("last_login_at", DateTime),
)

DEFAULT_ROLES = ["admin", "user", "viewer"]

# ─────────────────────────────────────────
# 해시 방식: 기존 users.json과 호환( salt + '::' + password )
def _hash_pw(password: str, salt: str) -> str:
    return hashlib.sha256((salt + "::" + password).encode("utf-8")).hexdigest()

def _now() -> datetime:
    return datetime.utcnow()

def _ensure_table():
    with session_scope() as s:
        bind = s.get_bind()
        _METADATA.create_all(bind, tables=[USERS])

# ─────────────────────────────────────────
# users.json → DB 1회 이관(유저 0명일 때만)
def _migrate_from_users_json_if_needed():
    # DB에 유저가 이미 있으면 종료
    with session_scope() as s:
        cnt = s.execute(select(func.count()).select_from(USERS)).scalar_one()
        if int(cnt or 0) > 0:
            return

    # 후보 경로: 서버 DB 폴더/users.json, 프로젝트 루트/users.json
    candidates: List[str] = []
    try:
        import settings
        db_dir = settings.get_db_dir()  # 서버 공유 경로일 가능성 높음
        if db_dir:
            candidates.append(os.path.join(db_dir, "users.json"))
    except Exception:
        pass
    candidates.append(os.path.abspath("./users.json"))

    src = next((p for p in candidates if p and os.path.isfile(p)), None)
    if not src:
        return

    try:
        with open(src, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
    except Exception:
        return

    records: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict) and isinstance(raw.get("users"), list):
        records = raw["users"]

    if not records:
        return

    with session_scope() as s:
        created = 0
        for u in records:
            name = (u.get("name") or "").strip()
            if not name:
                continue
            role = (u.get("role") or "user").strip().lower()
            if role not in DEFAULT_ROLES:
                role = "user"
            salt = (u.get("salt") or "").strip() or secrets.token_hex(8)
            pw_hash = (u.get("pw_hash") or "").strip()
            if not pw_hash:
                # users.json에 평문이었거나 비어 있으면 임시 비번
                pw_hash = _hash_pw("1234", salt)
            try:
                s.execute(insert(USERS).values(
                    name=name, role=role, email=None, is_active=True,
                    salt=salt, pw_hash=pw_hash,
                    created_at=_now(), updated_at=_now()
                ))
                created += 1
            except IntegrityError:
                s.rollback()
        s.commit()
    # 원본 users.json은 보관(백업 용도)

# ─────────────────────────────────────────
# 퍼블릭 API

def ensure_default_admin() -> None:
    """테이블 보장 + (유저 없으면) users.json 이관 + admin/1234 생성"""
    _ensure_table()
    _migrate_from_users_json_if_needed()
    with session_scope() as s:
        cnt = s.execute(select(func.count()).select_from(USERS)).scalar_one()
        if int(cnt or 0) == 0:
            salt = secrets.token_hex(8)
            s.execute(insert(USERS).values(
                name="admin", role="admin", email=None, is_active=True,
                salt=salt, pw_hash=_hash_pw("1234", salt),
                created_at=_now(), updated_at=_now()
            ))
            s.commit()

def verify(name: str, password: str) -> bool:
    _ensure_table()
    name = (name or "").strip()
    if not name or not password:
        return False
    with session_scope() as s:
        row = s.execute(
            select(USERS).where(USERS.c.name == name, USERS.c.is_active == True)
        ).mappings().first()
        if not row:
            return False
        ok = (_hash_pw(password, row["salt"]) == row["pw_hash"])
        if ok:
            s.execute(update(USERS).where(USERS.c.id == row["id"]).values(last_login_at=_now()))
            s.commit()
        return ok

def get_role(name: str) -> str:
    _ensure_table()
    with session_scope() as s:
        row = s.execute(select(USERS.c.role).where(USERS.c.name == name)).first()
        return (row[0] if row else "user")

def list_users() -> List[Dict[str, Any]]:
    _ensure_table()
    with session_scope() as s:
        rows = s.execute(select(
            USERS.c.id, USERS.c.name, USERS.c.role, USERS.c.email, USERS.c.is_active,
            USERS.c.created_at, USERS.c.updated_at, USERS.c.last_login_at
        ).order_by(USERS.c.name.asc())).mappings().all()
        return [dict(r) for r in rows]

# 기존 UI 호환용
def list_users_detailed() -> List[Dict[str, Any]]:
    return [{"name": u["name"], "role": u["role"]} for u in list_users()]

def create_user(name: str, password: str, role: str = "user", email: Optional[str]=None) -> None:
    _ensure_table()
    name = (name or "").strip()
    role = (role or "user").strip().lower()
    if role not in DEFAULT_ROLES:
        role = "user"
    if not name or not password:
        raise ValueError("이름/비밀번호가 비었습니다.")
    salt = secrets.token_hex(8)
    with session_scope() as s:
        try:
            s.execute(insert(USERS).values(
                name=name, role=role, email=(email or None), is_active=True,
                salt=salt, pw_hash=_hash_pw(password, salt),
                created_at=_now(), updated_at=_now()
            ))
            s.commit()
        except IntegrityError:
            s.rollback()
            raise ValueError("이미 존재하는 사용자입니다.")

# 기존 이름과 맞춰 제공(사용 중일 수 있으니)
def add_user(name: str, password: str, role: str = "user") -> None:
    create_user(name, password, role=role)

def change_password(name: str, new_password: str) -> None:
    _ensure_table()
    name = (name or "").strip()
    if not name or not new_password:
        raise ValueError("이름/비밀번호가 비었습니다.")
    salt = secrets.token_hex(8)
    with session_scope() as s:
        res = s.execute(update(USERS)
                        .where(USERS.c.name == name)
                        .values(salt=salt, pw_hash=_hash_pw(new_password, salt),
                                updated_at=_now()))
        if res.rowcount == 0:
            s.rollback()
            raise ValueError("사용자를 찾을 수 없습니다.")
        s.commit()

def set_role(name: str, role: str) -> None:
    _ensure_table()
    name = (name or "").strip()
    role = (role or "user").strip().lower()
    if role not in DEFAULT_ROLES:
        role = "user"
    with session_scope() as s:
        # 마지막 admin 보호
        row = s.execute(select(USERS).where(USERS.c.name == name)).mappings().first()
        if not row:
            raise ValueError("사용자를 찾을 수 없습니다.")
        if row["role"] == "admin" and role != "admin":
            admins = s.execute(select(func.count()).select_from(USERS).where(USERS.c.role=="admin", USERS.c.is_active==True)).scalar_one()
            if int(admins or 0) <= 1:
                raise ValueError("마지막 관리자 계정은 강등할 수 없습니다.")
        s.execute(update(USERS).where(USERS.c.id == row["id"])
                 .values(role=role, updated_at=_now()))
        s.commit()

def set_active(name: str, active: bool) -> None:
    _ensure_table()
    name = (name or "").strip()
    with session_scope() as s:
        # 마지막 admin 보호
        row = s.execute(select(USERS).where(USERS.c.name == name)).mappings().first()
        if not row:
            raise ValueError("사용자를 찾을 수 없습니다.")
        if row["role"] == "admin" and not active:
            admins = s.execute(select(func.count()).select_from(USERS).where(USERS.c.role=="admin", USERS.c.is_active==True)).scalar_one()
            if int(admins or 0) <= 1:
                raise ValueError("마지막 관리자 계정은 정지할 수 없습니다.")
        s.execute(update(USERS).where(USERS.c.id == row["id"])
                 .values(is_active=bool(active), updated_at=_now()))
        s.commit()

def delete_user(name: str) -> None:
    _ensure_table()
    name = (name or "").strip()
    with session_scope() as s:
        row = s.execute(select(USERS).where(USERS.c.name == name)).mappings().first()
        if not row:
            raise ValueError("사용자를 찾을 수 없습니다.")
        if row["role"] == "admin":
            admins = s.execute(select(func.count()).select_from(USERS).where(USERS.c.role=="admin")).scalar_one()
            if int(admins or 0) <= 1:
                raise ValueError("마지막 관리자 계정은 삭제할 수 없습니다.")
        s.execute(delete(USERS).where(USERS.c.id == row["id"]))
        s.commit()
