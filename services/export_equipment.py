from __future__ import annotations
import os
from typing import Optional
from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from services.equipment_service import list_equipment
from .exporter_common import header, autofit, fmt_date, EXPORT_DIR

def export_equipment_xlsx(keyword: str = "", path: Optional[str] = None) -> str:
    rows = list_equipment(keyword or "")
    wb = Workbook()
    ws: Worksheet = wb.active
    ws.title = "설비관리대장"

    # 헤더: '용도' 포함
    headers = [
        "설비번호","자산명","설비명","설비명 변경안","모델명",
        "크기(가로x세로x높이)mm","전압","전력용량(kWh)","유틸리티 AIR","유틸리티 냉각수","유틸리티 진공","유틸리티 기타",
        "제조회사","제조회사 대표 전화번호","제조일자","입고일(년)","입고일(월)","입고일(일)","수량","구입가격","설비위치",
        "용도",  # ← purpose
        "비고","파트"
    ]
    header(ws, 1, headers)

    for e in rows:
        ws.append([
            e.code or "", e.asset_name or "", e.name or "", e.alt_name or "", e.model or "",
            e.size_mm or "", e.voltage or "", e.power_kwh or "", e.util_air or "", e.util_coolant or "", e.util_vac or "", e.util_other or "",
            e.maker or "", e.maker_phone or "", fmt_date(e.manufacture_date) if e.manufacture_date else "",
            e.in_year or "", e.in_month or "", e.in_day or "", e.qty or "", e.purchase_price or "",
            e.location or "",
            e.purpose or "",   # ← 수정: 용도 = purpose
            e.note or "", e.part or ""
        ])

    autofit(ws)

    if not path:
        path = os.path.join(EXPORT_DIR, "설비관리대장_내보내기.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path
