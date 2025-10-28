from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

import os
from sqlalchemy import select, or_, func
from sqlalchemy.orm import load_only

from db import session_scope
from models import Equipment, Repair, Photo, EquipmentAccessory


# ------------------------------------------------------------
# UI 테이블에 뿌릴 안전한 데이터 컨테이너(세션 닫혀도 OK)
# ------------------------------------------------------------
@dataclass
class EquipmentRow:
    id: int
    code: str
    asset_name: Optional[str]
    name: str
    alt_name: Optional[str]
    model: Optional[str]

    size_mm: Optional[str]
    voltage: Optional[str]
    power_kwh: Optional[float]

    util_air: Optional[str]
    util_coolant: Optional[str]
    util_vac: Optional[str]
    purpose: Optional[str]       # ★ 새 컬럼(용도)
    util_other: Optional[str]    # 유틸리티 기타

    maker: Optional[str]
    maker_phone: Optional[str]
    manufacture_date: Optional[str]

    in_year: Optional[int]
    in_month: Optional[int]
    in_day: Optional[int]

    qty: Optional[float]
    purchase_price: Optional[float]
    location: Optional[str]
    note: Optional[str]
    part: Optional[str]
    status: Optional[str]


# ------------------------------------------------------------
# 목록 조회
# ------------------------------------------------------------
def list_equipment(keyword: str = "",
                   status: str = "모두",
                   include_deleted: bool = False) -> List[EquipmentRow]:
    """
    설비관리대장 표용 데이터 조회.
    - purpose(용도) 포함해서 반환
    - 세션 종료 후에도 안전하도록 dataclass로 복사해서 리턴
    """
    kw = (keyword or "").strip()
    rows: List[EquipmentRow] = []

    with session_scope() as s:
        q = s.query(Equipment)

        # 삭제 필터
        if not include_deleted:
            q = q.filter((Equipment.is_deleted == 0) | (Equipment.is_deleted.is_(None)))

        # 상태 필터
        st = (status or "모두").strip()
        if st != "모두":
            q = q.filter(Equipment.status == st)

        # 키워드(간단 통합 검색)
        if kw:
            like = f"%{kw}%"
            q = q.filter(or_(
                Equipment.code.like(like),
                Equipment.asset_name.like(like),
                Equipment.name.like(like),
                Equipment.alt_name.like(like),
                Equipment.model.like(like),
                Equipment.location.like(like),
                Equipment.part.like(like),
                Equipment.purpose.like(like),      # ★ 용도 검색도 포함
                Equipment.util_other.like(like),
            ))

        # 가볍게 필요한 컬럼만 로드(★ purpose 포함)
        q = q.options(load_only(
            Equipment.id, Equipment.code, Equipment.asset_name, Equipment.name, Equipment.alt_name,
            Equipment.model, Equipment.size_mm, Equipment.voltage, Equipment.power_kwh,
            Equipment.util_air, Equipment.util_coolant, Equipment.util_vac,
            Equipment.purpose,            # ★
            Equipment.util_other,
            Equipment.maker, Equipment.maker_phone, Equipment.manufacture_date,
            Equipment.in_year, Equipment.in_month, Equipment.in_day,
            Equipment.qty, Equipment.purchase_price, Equipment.location, Equipment.note,
            Equipment.part, Equipment.status,
            Equipment.is_deleted,
        )).order_by(Equipment.code.asc())

        for e in q.all():
            rows.append(EquipmentRow(
                id=e.id,
                code=e.code or "",
                asset_name=e.asset_name,
                name=e.name or "",
                alt_name=e.alt_name,
                model=e.model,
                size_mm=e.size_mm,
                voltage=e.voltage,
                power_kwh=e.power_kwh,
                util_air=e.util_air,
                util_coolant=e.util_coolant,
                util_vac=e.util_vac,
                purpose=getattr(e, "purpose", None),   # ★ 안전 접근
                util_other=e.util_other,
                maker=e.maker,
                maker_phone=e.maker_phone,
                manufacture_date=str(e.manufacture_date) if e.manufacture_date else None,
                in_year=e.in_year, in_month=e.in_month, in_day=e.in_day,
                qty=e.qty, purchase_price=e.purchase_price,
                location=e.location, note=e.note, part=e.part,
                status=e.status,
            ))
    return rows


# ------------------------------------------------------------
# 단건 조회 (편집/이력창 등)
# ------------------------------------------------------------
def get_equipment_by_code(code: str) -> Optional[Equipment]:
    with session_scope() as s:
        e = s.execute(
            select(Equipment).where(Equipment.code == code)
        ).scalars().first()
        if not e:
            return None
        # 필요한 필드 접근해서 미리 고정 (세션 밖에서 쓰는 경우 대비)
        _ = (
            e.asset_name, e.name, e.alt_name, e.model, e.size_mm, e.voltage, e.power_kwh,
            e.util_air, e.util_coolant, e.util_vac, e.util_other,
            getattr(e, "purpose", None),  # ★ 용도 접근
            e.maker, e.maker_phone, e.manufacture_date,
            e.in_year, e.in_month, e.in_day, e.qty, e.purchase_price,
            e.location, e.note, e.part, e.status
        )
        # 세션 내 객체를 반환해도 UI 쪽에서는 즉시 값만 읽고 끝이라 문제 없음.
        return e


# ------------------------------------------------------------
# 생성/수정/상태 변경/삭제
# ------------------------------------------------------------
def add_equipment(code: str, name: str = "") -> Equipment:
    with session_scope() as s:
        e = Equipment(code=code, name=name or code)
        s.add(e); s.flush()
        return e


def update_status(code: str, status: str) -> None:
    with session_scope() as s:
        e = s.execute(select(Equipment).where(Equipment.code == code)).scalars().first()
        if not e:
            raise ValueError(f"설비를 찾을 수 없습니다: {code}")
        e.status = status or None


def get_delete_preview(code: str) -> Tuple[int, int, int]:
    with session_scope() as s:
        e = s.execute(select(Equipment).where(Equipment.code == code)).scalars().first()
        if not e:
            return (0, 0, 0)
        rep = s.query(func.count(Repair.id)).filter(Repair.equipment_id == e.id).scalar() or 0
        ph  = s.query(func.count(Photo.id)).filter(Photo.equipment_id == e.id).scalar() or 0
        acc = s.query(func.count(EquipmentAccessory.id)).filter(EquipmentAccessory.equipment_id == e.id).scalar() or 0
        return (rep, ph, acc)


def delete_equipment_by_code(code: str, mode: str = "soft") -> None:
    """
    mode = "soft" → 보관함 이동(is_deleted=1)
    mode = "hard" → 완전삭제(관련 항목 포함)
    """
    with session_scope() as s:
        e = s.execute(select(Equipment).where(Equipment.code == code)).scalars().first()
        if not e:
            return
        if mode == "hard":
            s.delete(e)
        else:
            e.is_deleted = 1


# ------------------------------------------------------------
# 파일/폴더 유틸(프로젝트에 맞춰 필요 시 수정)
# ------------------------------------------------------------
def ensure_equipment_folder(code: str) -> str:
    """
    설비별 폴더를 만들어야 할 때 사용.
    프로젝트에 따라 root 경로를 settings 등에서 가져오면 됨.
    지금은 간단히 ./data/equipment/{code} 로 생성.
    """
    root = os.path.join(os.path.dirname(__file__), "..", "data", "equipment")
    path = os.path.abspath(os.path.join(root, code))
    os.makedirs(path, exist_ok=True)
    return path
