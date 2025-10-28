from __future__ import annotations
from typing import List, Optional
from sqlalchemy import text
from db import session_scope

def list_reason_codes() -> List[dict]:
    with session_scope() as s:
        rows = s.execute(text("SELECT id, name, favorite FROM reason_code ORDER BY favorite DESC, name ASC")).mappings().all()
        return [dict(r) for r in rows]

def add_reason_code(name: str, favorite: bool = False) -> int:
    name = (name or "").strip()
    if not name:
        return 0
    with session_scope() as s:
        s.execute(text("INSERT INTO reason_code(name, favorite) VALUES (:n, :f)"), {"n": name, "f": 1 if favorite else 0})
        rid = s.execute(text("SELECT last_insert_rowid()")).scalar()
        return int(rid or 0)

def toggle_favorite(reason_id: int) -> None:
    with session_scope() as s:
        s.execute(text("""
            UPDATE reason_code
            SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END
            WHERE id = :i
        """), {"i": int(reason_id)})

def delete_reason_code(reason_id: int) -> None:
    with session_scope() as s:
        s.execute(text("DELETE FROM reason_code WHERE id=:i"), {"i": int(reason_id)})

def ensure_seed():
    # db.ensure_db()에서 이미 기본값 시드함. 필요 시 확장용
    pass
