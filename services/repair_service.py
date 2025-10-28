from __future__ import annotations
from typing import Iterable, Optional
from types import SimpleNamespace

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from db import session_scope
from models import Repair, RepairItem, Equipment, ChangeLog
from services.consumable_service import adjust_stock

def _current_user() -> str | None:
    try:
        import user_session
        u = user_session.get_current_user()
        return getattr(u, "name", None)
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────
# 조회(세션 안전: DTO 반환)
def list_repairs(equipment_id: int) -> list[SimpleNamespace]:
    with session_scope() as s:
        rows = (
            s.execute(
                select(Repair)
                .options(selectinload(Repair.items))
                .where(Repair.equipment_id == equipment_id)
                .order_by(Repair.work_date.desc(), Repair.id.desc())
            )
            .scalars()
            .all()
        )
        out: list[SimpleNamespace] = []
        for r in rows:
            items_dto = [
                SimpleNamespace(
                    consumable_id=int(it.consumable_id),
                    qty=float(it.qty or 0.0),
                ) for it in (r.items or [])
            ]
            out.append(SimpleNamespace(
                id=int(r.id),
                equipment_id=int(r.equipment_id),
                work_date=r.work_date,
                kind=r.kind or "",
                title=r.title or "",
                detail=r.detail or "",
                vendor=getattr(r, "vendor", "") or "",
                work_hours=float(getattr(r, "work_hours", 0.0) or 0.0),
                complete_date=getattr(r, "complete_date", None),
                progress_status=getattr(r, "progress_status", None),
                items=items_dto,
            ))
        return out

def get_repair(rid: int) -> Optional[SimpleNamespace]:
    with session_scope() as s:
        r = (
            s.execute(
                select(Repair)
                .options(selectinload(Repair.items))
                .where(Repair.id == rid)
            )
            .scalars()
            .first()
        )
        if not r:
            return None

        items_dto = [
            SimpleNamespace(
                consumable_id=int(it.consumable_id),
                qty=float(it.qty or 0.0),
            ) for it in (r.items or [])
        ]
        return SimpleNamespace(
            id=int(r.id),
            equipment_id=int(r.equipment_id),
            work_date=r.work_date,
            kind=r.kind or "",
            title=r.title or "",
            detail=r.detail or "",
            vendor=getattr(r, "vendor", "") or "",
            work_hours=float(getattr(r, "work_hours", 0.0) or 0.0),
            complete_date=getattr(r, "complete_date", None),
            progress_status=getattr(r, "progress_status", None),
            items=items_dto,
        )

# ─────────────────────────────────────────────────────────────
# 입력/수정 (반드시 ID(int) 반환)
def add_repair(
    equipment_id: int,
    work_date,
    kind: str,
    detail: str,
    items: Iterable[tuple[int, float]] = (),
    *,
    title: str = "",
    progress_status: Optional[str] = None,
    complete_date=None,
    vendor: Optional[str] = None,
    work_hours: Optional[float] = None,
) -> int:
    with session_scope() as s:
        # 설비 존재 확인
        eq = s.get(Equipment, equipment_id)
        if not eq:
            raise ValueError(f"equipment_id {equipment_id} not found")

        r = Repair(
            equipment_id=equipment_id,
            work_date=work_date,
            kind=kind,
            title=(title or "").strip(),
            detail=(detail or "").strip(),
            progress_status=progress_status,
            complete_date=complete_date,
            vendor=vendor,
            work_hours=work_hours,
        )
        s.add(r); s.flush()  # r.id 확정

        # 소모품 처리 + 재고 반영
        new_map: dict[int, float] = {}
        for cid, qty in (items or ()):
            cid = int(cid); qty = float(qty or 0.0)
            if qty <= 0:
                continue
            new_map[cid] = new_map.get(cid, 0.0) + qty

        for cid, qty in new_map.items():
            s.add(RepairItem(repair_id=r.id, consumable_id=cid, qty=qty))
            adjust_stock(cid, qty=-qty, reason="수리 사용", related_repair_id=r.id)

        # ChangeLog (create)
        user = _current_user()
        for field, val in dict(
            work_date=work_date, kind=kind, title=title, detail=detail,
            vendor=vendor, work_hours=work_hours, progress_status=progress_status, complete_date=complete_date
        ).items():
            s.add(ChangeLog(module="repair", record_id=int(r.id), field=field, before=None, after=None if val is None else str(val), user=user))
        if new_map:
            s.add(ChangeLog(
                module="repair", record_id=int(r.id), field="items",
                before=None, after=", ".join([f"{cid}:{qty}" for cid, qty in new_map.items()]), user=user
            ))

        return int(r.id)

def update_repair(
    rid: int,
    *,
    equipment_id: Optional[int] = None,
    work_date=None,
    kind: Optional[str] = None,
    detail: Optional[str] = None,
    items: Optional[Iterable[tuple[int, float]]] = None,
    title: Optional[str] = None,
    progress_status: Optional[str] = None,
    complete_date=None,
    vendor: Optional[str] = None,
    work_hours: Optional[float] = None,
) -> int:
    with session_scope() as s:
        r = s.get(Repair, rid)
        if not r:
            raise ValueError(f"repair_id {rid} not found")

        before = dict(
            equipment_id=r.equipment_id, work_date=r.work_date, kind=r.kind, title=r.title, detail=r.detail,
            progress_status=r.progress_status, complete_date=r.complete_date, vendor=r.vendor, work_hours=r.work_hours
        )
        if items is not None:
            old_map: dict[int, float] = {}
            for it in (r.items or []):
                old_map[int(it.consumable_id)] = old_map.get(int(it.consumable_id), 0.0) + float(it.qty or 0.0)
        else:
            old_map = {}

        if equipment_id is not None: r.equipment_id = equipment_id
        if work_date is not None:    r.work_date = work_date
        if kind is not None:         r.kind = kind
        if title is not None:        r.title = (title or "").strip()
        if detail is not None:       r.detail = (detail or "").strip()
        if progress_status is not None: r.progress_status = progress_status
        if complete_date is not None:   r.complete_date = complete_date
        if vendor is not None:       r.vendor = vendor
        if work_hours is not None:   r.work_hours = work_hours

        # 소모품/재고 재계산
        new_map: dict[int, float] = {}
        if items is not None:
            for cid, qty in (items or []):
                cid = int(cid); qty = float(qty or 0.0)
                if qty <= 0: continue
                new_map[cid] = new_map.get(cid, 0.0) + qty

            # 차이만큼 재고 가감
            all_keys = set(old_map) | set(new_map)
            for cid in all_keys:
                before_qty = old_map.get(cid, 0.0)
                after_qty  = new_map.get(cid, 0.0)
                diff   = after_qty - before_qty
                if abs(diff) <= 1e-9:
                    continue
                if diff > 0:
                    adjust_stock(cid, qty=-abs(diff), reason="수리 사용", related_repair_id=r.id)
                else:
                    adjust_stock(cid, qty=+abs(diff), reason=None, related_repair_id=r.id)

            # 항목 재기록
            s.execute(delete(RepairItem).where(RepairItem.repair_id == r.id))
            for cid, qty in new_map.items():
                s.add(RepairItem(repair_id=r.id, consumable_id=cid, qty=qty))

        # ChangeLog (diff)
        user = _current_user()
        after = dict(
            equipment_id=r.equipment_id, work_date=r.work_date, kind=r.kind, title=r.title, detail=r.detail,
            progress_status=r.progress_status, complete_date=r.complete_date, vendor=r.vendor, work_hours=r.work_hours
        )
        for k in after.keys():
            if before.get(k) != after.get(k):
                s.add(ChangeLog(
                    module="repair", record_id=int(r.id), field=k,
                    before=None if before.get(k) is None else str(before.get(k)),
                    after=None if after.get(k) is None else str(after.get(k)),
                    user=user
                ))
        if items is not None and old_map != new_map:
            def fmt(m): return ", ".join([f"{cid}:{qty}" for cid, qty in sorted(m.items())])
            s.add(ChangeLog(module="repair", record_id=int(r.id), field="items", before=fmt(old_map), after=fmt(new_map), user=user))

        return int(r.id)

# ─────────────────────────────────────────────────────────────
# 삭제 (하드 삭제 + 사용 소모품 재고 복원)
def delete_repair(rid: int, *, reverse_stock: bool = True) -> int:
    """
    - Repair / RepairItem / RepairPhoto 를 **하드 삭제**합니다.
    - reverse_stock=True 이면, 사용했던 소모품 재고를 되돌립니다(+수량).
    - 성공 시 rid 반환, 없으면 ValueError.
    """
    with session_scope() as s:
        r: Repair | None = (
            s.execute(
                select(Repair)
                .options(selectinload(Repair.items))
                .where(Repair.id == rid)
            )
            .scalars()
            .first()
        )
        if not r:
            raise ValueError(f"repair_id {rid} not found")

        if reverse_stock:
            for it in (r.items or []):
                try:
                    adjust_stock(int(it.consumable_id), qty=+float(it.qty or 0.0),
                                 reason="수리 내역 삭제 복원", related_repair_id=rid)
                except Exception:
                    pass

        s.delete(r)
        user = _current_user()
        s.add(ChangeLog(module="repair", record_id=int(rid), field="delete", before=None, after="deleted", user=user))
        return int(rid)

def delete_repairs_bulk(rids: Iterable[int], *, reverse_stock: bool = True) -> int:
    """
    여러 건 삭제. 개수 반환.
    """
    count = 0
    for rid in (rids or []):
        try:
            delete_repair(int(rid), reverse_stock=reverse_stock)
            count += 1
        except Exception:
            pass
    return count
