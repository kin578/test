from __future__ import annotations
import pandas as pd
import re
from typing import Any, Optional
from datetime import datetime
from models import init_db, Equipment
from db import session_scope
from sqlalchemy import select

# ── 공통 유틸
def pick(row:dict, keys:list[str]) -> Any:
    for k in keys:
        if k in row and pd.notna(row[k]):
            v = row[k]
            if isinstance(v, str):
                v = v.strip()
            return v
    return None

def parse_int(x) -> Optional[int]:
    try:
        if x is None or (isinstance(x, str) and x.strip()==""):
            return None
        return int(float(str(x).strip()))
    except Exception:
        return None

def parse_float(x) -> Optional[float]:
    if x is None: return None
    s = str(x).replace(",", "")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "."): return None
    try:
        return float(s)
    except Exception:
        return None

def parse_date(value):
    if value in (None, ""): return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None

def parse_datetime(value) -> Optional[datetime]:
    if value in (None, ""): return None
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────
# 설비 (용도=purpose / 유틸리티 기타=util_other)
def import_equipment_xlsx(path:str):
    df = pd.read_excel(path, dtype=str).fillna("")
    for _, r in df.iterrows():
        row = r.to_dict()

        no = parse_int(pick(row, ["NO","No","no"]))
        code = pick(row, ["설비번호","관리번호","설비코드","코드","code","Code"]) or ""
        if not code:
            continue

        asset_name = pick(row, ["자산명","asset_name","AssetName"])
        name = pick(row, ["설비명","장비명","name","Name"]) or ""
        alt_name = pick(row, ["설비명 변경안","설비명변경안","변경안","alt_name","AltName"])
        model = pick(row, ["모델명","모델","Model","형식","type","Type"])

        size_mm = pick(row, ["크기(가로x세로x높이)mm","크기","규격(mm)","규격","size","Size"])
        voltage = pick(row, ["전압","voltage","Voltage"])
        power_kwh = parse_float(pick(row, ["전력용량(Kwh)","전력용량(kWh)","전력용량","전력(kW)","kW","power","Power"]))

        util_air = pick(row, ["유틸리티 AIR","유틸리티AIR","AIR","air"])
        util_coolant = pick(row, ["유틸리티 냉각수","냉각수","coolant","Coolant"])
        util_vac = pick(row, ["유틸리티 진공","진공","vacuum","Vacuum"])
        # ★ util_other 후보(‘용도’는 제외!)
        util_other = pick(row, [
            "유틸리티 기타","기타유틸리티","유틸리티","Util","util"
        ])
        # ★ purpose 후보(‘용도’만!)
        purpose = pick(row, [
            "용도","용 도","purpose","Purpose","usage","Usage","用途"
        ])

        maker = pick(row, ["제조회사","제조사","Maker","maker"])
        maker_phone = pick(row, ["제조회사 대표 전화번호","대표 전화","제조사 전화","Tel","tel","전화","전화번호","Phone","phone"])
        manufacture_date = parse_date(pick(row, ["제조일자","제작일자","제작일","manufacture_date","ManufactureDate"]))

        in_year = parse_int(pick(row, ["입고일(년)","입고년","in_year","InYear"]))
        in_month = parse_int(pick(row, ["입고일(월)","입고월","in_month","InMonth"]))
        in_day = parse_int(pick(row, ["입고일(일)","입고일","in_day","InDay"]))

        qty = parse_float(pick(row, ["수량","qty","Qty"]))
        purchase_price = parse_float(pick(row, ["구입가격","구매가격","가격","price","Price"]))
        location = pick(row, ["설비위치","위치","location","Location"])
        note = pick(row, ["비고","메모","특이사항","note","Note"])
        part = pick(row, ["파트","부서","라인","part","Part"])

        with session_scope() as s:
            eq = s.execute(select(Equipment).where(Equipment.code==code)).scalars().first()
            if not eq:
                eq = Equipment(code=code, name=name)
                s.add(eq)
                s.flush()

            eq.no = no
            eq.asset_name = asset_name or None
            eq.name = name or eq.name
            eq.alt_name = alt_name or None
            eq.model = model or None

            eq.size_mm = size_mm or None
            eq.voltage = voltage or None
            eq.power_kwh = power_kwh

            eq.util_air = util_air or None
            eq.util_coolant = util_coolant or None
            eq.util_vac = util_vac or None
            eq.util_other = util_other or None         # 유틸리티 기타
            eq.purpose = purpose or None               # ★ 용도

            eq.maker = maker or None
            eq.maker_phone = maker_phone or None
            eq.manufacture_date = manufacture_date

            eq.in_year = in_year
            eq.in_month = in_month
            eq.in_day = in_day

            eq.qty = qty
            eq.purchase_price = purchase_price
            eq.location = location or None
            eq.note = note or None
            eq.part = part or None

# ─────────────────────────────────────────────────────────────
# 소모품 마스터 가져오기(합쳐 넣기)
def import_consumables_xlsx(path:str) -> int:
    from services.consumable_service import upsert_consumable
    df = pd.read_excel(path, dtype=str).fillna("")
    n = 0
    for _, r in df.iterrows():
        row = r.to_dict()
        name = pick(row, ["품목","소모품명","항목"]) or ""
        if not name.strip():
            continue
        spec = pick(row, ["규격","사양","Spec"]) or ""
        stock_qty = parse_float(pick(row, ["현재고","재고","Stock"]))
        min_qty = parse_float(pick(row, ["안전수량","최저재고","MinQty"])) or 0.0
        note = pick(row, ["비고","메모"]) or ""

        upsert_consumable(
            name=name.strip(),
            spec=spec.strip(),
            min_qty=min_qty,
            note=note.strip(),
            stock_qty=stock_qty,
        )
        n += 1
    return n

# ─────────────────────────────────────────────────────────────
def import_consumable_txn_xlsx(path: str) -> int:
    from services.consumable_service import upsert_consumable, adjust_stock

    df = pd.read_excel(path, dtype=str).fillna("")
    n = 0
    for _, r in df.iterrows():
        row = r.to_dict()
        name = (row.get("품목") or row.get("소모품명") or row.get("항목") or "").strip()
        if not name:
            continue
        spec = (row.get("규격") or row.get("사양") or row.get("Spec") or "").strip()
        io = (row.get("입출고") or "").strip()  # "입고" 또는 "출고"
        qty = parse_float(row.get("수량"))
        when = parse_datetime(row.get("거래일시")) or datetime.now()
        reason = (row.get("사유") or "").strip() if io == "출고" else None
        related_id = parse_int(row.get("관련 수리ID"))

        c = upsert_consumable(name=name, spec=spec)  # 없으면 생성
        if not qty or qty == 0:
            continue

        if io == "입고":
            adjust_stock(consumable_id=c.id, qty=+abs(qty), reason=None,
                         related_repair_id=related_id, when=when)
        else:
            adjust_stock(consumable_id=c.id, qty=-abs(qty), reason=reason or None,
                         related_repair_id=related_id, when=when)
        n += 1
    return n

# ─────────────────────────────────────────────────────────────
def import_repairs_xlsx(path:str):
    pass

def ensure_db():
    init_db()
