from __future__ import annotations
import os
from typing import Optional
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select

from db import session_scope
from models import Consumable
from .exporter_common import header, autofit, EXPORT_DIR, TEMPLATES_DIR

def export_consumables_xlsx(path: Optional[str] = None) -> str:
    wb = Workbook(); ws: Worksheet = wb.active
    ws.title = "소모품"
    header(ws, 1, ["품목","규격","현재고","안전수량","비고","ID"])
    with session_scope() as s:
        rows = s.execute(select(Consumable).order_by(Consumable.name.asc(), Consumable.spec.asc())).scalars().all()
        for c in rows:
            ws.append([c.name or "", c.spec or "", c.stock_qty or 0, c.min_qty or 0, getattr(c, "note", "") or "", c.id or ""])
    autofit(ws)
    if not path:
        path = os.path.join(EXPORT_DIR, "소모품_목록.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path

def save_consumable_template_xlsx(path: Optional[str] = None) -> str:
    wb = Workbook(); ws: Worksheet = wb.active
    ws.title = "소모품_양식"
    header(ws, 1, ["품목","규격","안전수량","비고"])
    ws.append(["예) 베어링","6202ZZ",10,"비고 메모"])
    autofit(ws)
    if not path:
        path = os.path.join(TEMPLATES_DIR, "소모품_양식.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path
