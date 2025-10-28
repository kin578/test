from __future__ import annotations
from typing import Iterable, List, Tuple, Optional
from types import SimpleNamespace

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from db import session_scope
from models import EquipmentAccessory


def list_accessories(equipment_id: int) -> List[SimpleNamespace]:
    """
    UI 바인딩이 안전하도록 DTO(SimpleNamespace)로 반환.
    """
    with session_scope() as s:
        rows = (
            s.execute(
                select(EquipmentAccessory)
                .where(EquipmentAccessory.equipment_id == equipment_id)
                .order_by(EquipmentAccessory.ord.asc(), EquipmentAccessory.id.asc())
            )
            .scalars()
            .all()
        )
        out: List[SimpleNamespace] = []
        for r in rows:
            out.append(
                SimpleNamespace(
                    id=int(getattr(r, "id", 0)),
                    equipment_id=int(getattr(r, "equipment_id", equipment_id)),
                    ord=int(getattr(r, "ord", 0) or 0),
                    name=getattr(r, "name", "") or "",
                    spec=getattr(r, "spec", "") or "",
                    note=getattr(r, "note", "") or "",
                )
            )
        return out


def _normalize_rows(rows: Iterable[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    """
    공백/빈값 정리 + 완전 빈행 제거.
    """
    out: List[Tuple[str, str, str]] = []
    for nm, sp, nt in (rows or []):
        nm = (nm or "").strip()
        sp = (sp or "").strip()
        nt = (nt or "").strip()
        if nm or sp or nt:
            out.append((nm, sp, nt))
    return out


def replace_accessories(
    equipment_id: int,
    rows: Iterable[Tuple[str, str, str]],
    *,
    session: Optional[Session] = None,
) -> None:
    """
    부속기구를 '전량 교체' 방식으로 저장.
    - 같은 트랜잭션을 쓰기 위해 session을 외부에서 전달받을 수 있음.
      (넘겨주지 않으면 내부에서 별도 세션을 열어 수행)
    - rows: (name, spec, note)
    """
    data = _normalize_rows(rows)

    if session is not None:
        _replace_accessories_in_session(session, equipment_id, data)
        return

    # 독립 실행용 (외부 세션이 없을 때만)
    with session_scope() as s:
        _replace_accessories_in_session(s, equipment_id, data)


def _replace_accessories_in_session(
    s: Session,
    equipment_id: int,
    data: List[Tuple[str, str, str]],
) -> None:
    # 기존 레코드 전량 삭제
    s.execute(delete(EquipmentAccessory).where(EquipmentAccessory.equipment_id == equipment_id))

    # 1..N 순번으로 삽입
    for i, (nm, sp, nt) in enumerate(data, start=1):
        s.add(
            EquipmentAccessory(
                equipment_id=equipment_id,
                ord=i,
                name=nm or "",
                spec=sp or "",
                note=nt or "",
            )
        )
    # flush는 호출자 쪽(commit 시)에서 함께 처리됨
