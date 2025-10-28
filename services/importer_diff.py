from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date

import pandas as pd
from PySide6.QtWidgets import QDialog
from sqlalchemy import select

from db import session_scope
from models import Equipment

# 기존 importer 유틸 재사용
from services.importer import pick, parse_int, parse_float, parse_date

# 비어 있으면 변경을 허용하지 않는 필수 필드(Non-NULL 제약과 매칭)
REQUIRED_NONEMPTY_FIELDS = {"name"}

def _normalize_none(s: Optional[str]) -> Optional[str]:
    """빈 문자열을 None으로 정규화"""
    if s is None:
        return None
    if isinstance(s, str) and s.strip() == "":
        return None
    return s

def _row_to_values(rowdict: dict) -> Tuple[str, Dict[str, Any]]:
    """
    엑셀 1행 → (코드, 필드 딕셔너리)
    - 비어 있는 문자열은 None으로 정규화
    """
    code = (pick(rowdict, ["설비번호","관리번호","설비코드","코드"]) or "").strip()

    d: Dict[str, Any] = {}
    d["asset_name"] = _normalize_none(pick(rowdict, ["자산명"]))
    d["name"] = _normalize_none(pick(rowdict, ["설비명","장비명"]))  # ← 필수(비어 있으면 적용 안 함)
    d["alt_name"] = _normalize_none(pick(rowdict, ["설비명 변경안","설비명변경안","변경안"]))
    d["model"] = _normalize_none(pick(rowdict, ["모델명","모델","Model","형식"]))

    d["size_mm"] = _normalize_none(pick(rowdict, ["크기(가로x세로x높이)mm","크기","규격(mm)"]))
    d["voltage"] = _normalize_none(pick(rowdict, ["전압"]))
    d["power_kwh"] = parse_float(pick(rowdict, ["전력용량(Kwh)","전력용량(kWh)","전력용량"]))

    d["util_air"] = _normalize_none(pick(rowdict, ["유틸리티 AIR","유틸리티AIR","AIR"]))
    d["util_coolant"] = _normalize_none(pick(rowdict, ["유틸리티 냉각수","냉각수"]))
    d["util_vac"] = _normalize_none(pick(rowdict, ["유틸리티 진공","진공"]))
    d["util_other"] = _normalize_none(pick(rowdict, ["유틸리티 기타","기타유틸리티","유틸리티"]))  # 유틸리티 기타
    d["purpose"] = _normalize_none(pick(rowdict, ["용도"]))                                        # 용도

    d["maker"] = _normalize_none(pick(rowdict, ["제조회사","제조사","Maker"]))
    d["maker_phone"] = _normalize_none(pick(rowdict, ["제조회사 대표 전화번호","대표 전화","제조사 전화"]))
    d["manufacture_date"] = parse_date(pick(rowdict, ["제조일자","제작일자"]))

    d["in_year"] = parse_int(pick(rowdict, ["입고일(년)","입고년"]))
    d["in_month"] = parse_int(pick(rowdict, ["입고일(월)","입고월"]))  # ← 버그 수정(예전엔 월 파싱에 실수)
    d["in_day"] = parse_int(pick(rowdict, ["입고일(일)","입고일"]))

    d["qty"] = parse_float(pick(rowdict, ["수량"]))
    d["purchase_price"] = parse_float(pick(rowdict, ["구입가격","구매가격","가격"]))
    d["location"] = _normalize_none(pick(rowdict, ["설비위치","위치"]))
    d["note"] = _normalize_none(pick(rowdict, ["비고","메모","특이사항"]))
    d["part"] = _normalize_none(pick(rowdict, ["파트","부서","라인"]))

    return code, d

def _read_excel(path: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, dtype=object).fillna("")
    return [dict(r) for _, r in df.iterrows()]

def import_equipment_xlsx_diff(path: str, parent=None) -> tuple[int,int,int]:
    """
    엑셀 왕복 머지(미리보기)
    Returns: (created_count, diff_count, applied_count)
    """
    rows = _read_excel(path)
    created = 0
    diffs: List[Dict[str, Any]] = []

    with session_scope() as s:
        for row in rows:
            code, vals = _row_to_values(row)
            if not code:
                continue

            eq = s.execute(select(Equipment).where(Equipment.code==code)).scalars().first()
            if not eq:
                # 신규는 name이 비어 있으면 코드로 대체
                new_name = (vals.get("name") or code)
                eq = Equipment(code=code, name=new_name)
                s.add(eq); s.flush()
                # 선택적으로 나머지 필드 바로 저장(신규는 충돌 없음)
                for k, v in vals.items():
                    if k == "name":
                        setattr(eq, "name", new_name)
                    elif k != "code":
                        setattr(eq, k, v)
                created += 1
                continue

            # 기존 설비는 변경점만 수집
            for field, newval in vals.items():
                if field == "code":
                    continue
                # ★ 필수 필드는 비어 있으면 '변경하지 않음'
                if field in REQUIRED_NONEMPTY_FIELDS and _normalize_none(newval) is None:
                    continue
                oldval = getattr(eq, field, None)
                if (oldval or None) == (newval or None):
                    continue
                diffs.append({
                    "equipment_id": eq.id,
                    "code": code,
                    "field": field,
                    "old": oldval,
                    "new": newval,
                })
        s.commit()  # 신규 생성 커밋

    diff_count = len(diffs)
    if diff_count == 0:
        return (created, 0, 0)

    # 미리보기 다이얼로그 (없으면 전부 적용)
    try:
        from ui.dialogs.diff_merge_dialog import DiffMergeDialog
        dlg = DiffMergeDialog(diffs, created_count=created, parent=parent)
        if dlg.exec() != QDialog.Accepted:
            return (created, diff_count, 0)
        selected = dlg.get_selected_diffs()
    except Exception:
        selected = diffs

    # ★ 적용 전: 필수필드 비우는 변경 제거
    filtered: List[Dict[str, Any]] = []
    for d in selected:
        if d["field"] in REQUIRED_NONEMPTY_FIELDS and _normalize_none(d["new"]) is None:
            # 설비명 같은 필수 필드를 비우려는 변경은 무시
            continue
        filtered.append(d)

    # 선택 사항이 모두 필터링되면 종료
    if not filtered:
        return (created, diff_count, 0)

    # 적용
    from collections import defaultdict
    by_id: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for d in filtered:
        by_id[int(d["equipment_id"])].append(d)

    applied = 0
    with session_scope() as s:
        for eid, changes in by_id.items():
            eq = s.get(Equipment, int(eid))
            if not eq:
                continue
            for d in changes:
                setattr(eq, d["field"], d["new"])
                applied += 1
        s.commit()

    return (created, diff_count, applied)
