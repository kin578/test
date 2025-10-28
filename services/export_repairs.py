# services/export_repairs.py
from __future__ import annotations
from datetime import date, datetime
import os
from typing import Optional, Iterable, Dict

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from db import session_scope
from models import Equipment, Repair, RepairItem, Consumable
from .exporter_common import header, autofit, fmt_date, EXPORT_DIR


def export_repairs_xlsx(
    path: Optional[str] = None,
    equipment_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    columns: Optional[Iterable[str]] = None,
) -> str:
    """
    개선·수리 탭 내보내기
    - equipment_id: 해당 설비만 필터
    - date_from/date_to: 기간 필터(둘 중 하나만 줘도 됨)
    - columns: 내보낼 컬럼 순서를 바꾸고 싶으면 리스트로 전달(없으면 기본)
    """
    default_cols = [
        "설비코드","설비명","일자","구분","제목","내용",
        "사용소모품수","사용소모품상세","완료일자","진행현황","등록시각","수리ID"
    ]
    headers = list(columns) if columns else default_cols

    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "개선·수리"
    header(ws, 1, headers)

    with session_scope() as s:
        stmt = (
            select(Repair)
            .options(selectinload(Repair.items), selectinload(Repair.equipment))
        )
        if equipment_id:
            stmt = stmt.where(Repair.equipment_id == int(equipment_id))
        if date_from:
            stmt = stmt.where(Repair.work_date >= date_from)
        if date_to:
            stmt = stmt.where(Repair.work_date <= date_to)
        stmt = stmt.order_by(Repair.work_date.asc(), Repair.id.asc())

        rows = s.execute(stmt).scalars().unique().all()

        def items_detail(r: Repair) -> str:
            if not r.items:
                return ""
            cids = list({it.consumable_id for it in r.items if it.consumable_id})
            name_map: Dict[int, str] = {}
            if cids:
                for c in s.execute(select(Consumable).where(Consumable.id.in_(cids))).scalars().all():
                    name_map[c.id] = f"{c.name or ''} / {c.spec or ''}".strip()
            parts = []
            for it in r.items:
                label = name_map.get(it.consumable_id, f"ID:{it.consumable_id}")
                parts.append(f"{label} x {it.qty}")
            return "; ".join(parts)

        for r in rows:
            eq = r.equipment or Equipment()
            vals = {
                "설비코드": eq.code or "",
                "설비명": eq.name or "",
                "일자": fmt_date(r.work_date),
                "구분": r.kind or "",
                "제목": r.title or "",
                "내용": r.detail or "",
                "사용소모품수": len(r.items or []),
                "사용소모품상세": items_detail(r),
                "완료일자": fmt_date(getattr(r, "complete_date", None)),
                "진행현황": getattr(r, "progress_status", "") or "",
                "등록시각": fmt_date(getattr(r, "created_at", None)),
                "수리ID": r.id,
            }
            ws.append([vals.get(h, "") for h in headers])

    autofit(ws)
    if not path:
        path = os.path.join(EXPORT_DIR, "개선수리_내보내기.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path
