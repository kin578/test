from __future__ import annotations
from typing import Optional, Tuple
from types import SimpleNamespace
import os
import pandas as pd
from sqlalchemy import select, delete, text

from db import session_scope
from models import Consumable

# ConsumableTxn 이 없을 수도 있으므로 선택적 임포트
try:
    from models import ConsumableTxn  # 있으면 사용
    HAS_TXN = True
except Exception:
    ConsumableTxn = None              # 없으면 로그 생략 또는 안전 SQL만 사용
    HAS_TXN = False

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXPORT_DIR = os.path.join(APP_ROOT, "exports")
TEMPLATES_DIR = os.path.join(APP_ROOT, "templates")
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 부동소수 안정 처리
EPS = 1e-6
def _is_zero(x: float | None) -> bool:
    try:
        return abs(float(x or 0.0)) <= EPS
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────
# 현재 DB의 consumable_txn 실제 컬럼(레거시 대응)
def _txn_columns(s) -> set[str]:
    cols = set()
    try:
        rows = s.execute(text("PRAGMA table_info(consumable_txn)")).all()
        for _cid, name, *_ in rows:
            cols.add(str(name))
    except Exception:
        pass
    return cols

def _insert_txn_safe(
    s,
    consumable_id: int,
    qty: float,
    reason: Optional[str],
    related_repair_id: Optional[int],
    when_dt,  # datetime
):
    """
    consumable_txn 테이블이 존재하고, 해당 컬럼이 있을 때만 안전하게 INSERT.
    - txn_time / created_at 컬럼이 있으면 when_dt로 채움
    - 테이블이 없거나 컬럼이 없으면 아무 것도 하지 않음(에러 없음)
    """
    cols = _txn_columns(s)
    if not cols:
        return

    names = ["consumable_id", "qty"]
    params = {"consumable_id": int(consumable_id), "qty": float(qty)}

    if "reason" in cols:
        names.append("reason"); params["reason"] = (reason or None)
    if "related_repair_id" in cols:
        names.append("related_repair_id"); params["related_repair_id"] = related_repair_id
    if "txn_time" in cols:
        names.append("txn_time"); params["txn_time"] = when_dt
    if "created_at" in cols:
        names.append("created_at"); params["created_at"] = when_dt

    cols_sql = ", ".join(names)
    ph = ", ".join([f":{k}" for k in names])
    s.execute(text(f"INSERT INTO consumable_txn ({cols_sql}) VALUES ({ph})"), params)

# ─────────────────────────────────────────────────────────────
# 조회 (세션 안전: DTO로 반환, 컬럼 유무 무관)
def list_consumables(keyword: str = "") -> list[SimpleNamespace]:
    """
    ✅ 세션 안에서 ORM → SimpleNamespace 로 변환해서 반환
       (세션 종료 후에도 안전하게 속성 접근 가능)
    """
    kw = (keyword or "").strip().lower()
    with session_scope() as s:
        rows = s.execute(select(Consumable).order_by(Consumable.id.asc())).scalars().all()
        out: list[SimpleNamespace] = []
        for r in rows:
            name = getattr(r, "name", "") or ""
            spec = getattr(r, "spec", "") or ""
            if kw and (kw not in name.lower()) and (kw not in spec.lower()):
                continue
            out.append(SimpleNamespace(
                id=getattr(r, "id", None),
                name=name,
                spec=spec,
                stock_qty=float(getattr(r, "stock_qty", 0.0) or 0.0),
                min_qty=float(getattr(r, "min_qty", 0.0) or 0.0),  # ← 컬럼 없어도 0.0
                note=getattr(r, "note", "") or ""
            ))
        return out  # ← 세션 안에서 변환 끝!

def get_consumable(cid: int) -> Optional[SimpleNamespace]:
    """
    ✅ 단건도 세션 안에서 안전 객체로 변환해 반환
    """
    with session_scope() as s:
        r = s.get(Consumable, int(cid))
        if not r:
            return None
        return SimpleNamespace(
            id=getattr(r, "id", None),
            name=getattr(r, "name", "") or "",
            spec=getattr(r, "spec", "") or "",
            stock_qty=float(getattr(r, "stock_qty", 0.0) or 0.0),
            min_qty=float(getattr(r, "min_qty", 0.0) or 0.0),
            note=getattr(r, "note", "") or ""
        )

# ─────────────────────────────────────────────────────────────
# 생성/수정(업서트) — 존재하는 컬럼만 안전하게 설정
def upsert_consumable(
    name: str,
    spec: str = "",
    min_qty: float = 0.0,
    note: str = "",
    cid: int | None = None,
    stock_qty: float | None = None,   # 가져올 때 현재고도 반영하고 싶을 때
) -> Consumable:
    with session_scope() as s:
        c: Consumable | None = None
        if cid:
            c = s.get(Consumable, int(cid))

        if not c:
            stmt = select(Consumable).where(
                Consumable.name == name,
                Consumable.spec == (spec or None),
            )
            c = s.execute(stmt).scalars().first()

        if not c:
            # 생성 시에는 안전하게 최소 필드만 생성 후 속성 셋(존재시만)
            c = Consumable(name=name, spec=(spec or None))
            if hasattr(c, "min_qty"):
                c.min_qty = float(min_qty or 0.0)
            if stock_qty is not None and hasattr(c, "stock_qty"):
                c.stock_qty = float(stock_qty)
            if hasattr(c, "note"):
                c.note = (note or None) if note else None
            s.add(c)
            s.flush()
        else:
            c.name = name
            c.spec = spec or None
            if hasattr(c, "min_qty"):
                c.min_qty = float(min_qty or 0.0)
            if stock_qty is not None and hasattr(c, "stock_qty"):
                c.stock_qty = float(stock_qty)
            if hasattr(c, "note"):
                c.note = note or None
        return c

# ─────────────────────────────────────────────────────────────
# 삭제
def delete_consumable(consumable_id: int, force: bool = False) -> None:
    with session_scope() as s:
        c = s.get(Consumable, consumable_id)
        if not c:
            raise ValueError("해당 소모품이 없습니다.")

        cur_qty = float(getattr(c, "stock_qty", 0.0) or 0.0)
        if cur_qty != 0.0 and not force:
            raise ValueError(f"재고가 0이 아닙니다. (현재고: {cur_qty})")

        # 입출고 이력 존재 검사 (ORM이 있을 때만 엄격 검사)
        has_txn = False
        if HAS_TXN:
            has_txn = s.execute(
                select(ConsumableTxn.id).where(ConsumableTxn.consumable_id == c.id)
            ).first() is not None

        if has_txn and not force:
            raise ValueError("입출고 이력이 있어 삭제할 수 없습니다.")

        if has_txn and force:
            s.execute(delete(ConsumableTxn).where(ConsumableTxn.consumable_id == c.id))

        s.execute(delete(Consumable).where(Consumable.id == c.id))

# ─────────────────────────────────────────────────────────────
# 재고 조정 (레거시 txn_time/created_at 제약까지 안전)
def adjust_stock(
    consumable_id: int,
    qty: float,
    reason: str = "",
    related_repair_id: int | None = None,
    when=None,  # datetime | None (엑셀에서 일시 지정 시 사용)
) -> Tuple[Optional[Consumable], Optional[object]]:
    """
    ✅ 중요: ConsumableTxn ORM이 있으면 우선 사용하고,
             실패 시(또는 ORM이 없으면) 재고는 적용하되
             안전 SQL로 이력 기록을 시도합니다(테이블/컬럼이 있으면).
    """
    from datetime import datetime as _dt
    if not qty or qty == 0:
        raise ValueError("수량(qty)은 0이 될 수 없습니다.")

    when = when or _dt.now()

    with session_scope() as s:
        # 1) 현재 재고 읽고 새 재고 계산
        c = s.get(Consumable, consumable_id)
        if not c:
            raise ValueError("해당 소모품이 없습니다.")

        if hasattr(c, "stock_qty"):
            cur = float(getattr(c, "stock_qty", 0.0) or 0.0)
            proposed = cur + float(qty)
            if proposed < -EPS:
                raise ValueError(f"재고 부족: 현재 {cur}, 요청 {qty}")
            # 근사 0 스냅
            if abs(proposed) <= EPS:
                proposed = 0.0
            setattr(c, "stock_qty", proposed)
        else:
            # stock 컬럼 자체가 없다면, 로그만 남기거나 skip
            proposed = None  # 알림용

        txn = None

        if HAS_TXN:
            # 3) 이력 ORM으로 시도
            try:
                txn = ConsumableTxn(
                    consumable_id=getattr(c, "id", consumable_id),
                    qty=float(qty),
                    reason=reason or None,
                    related_repair_id=related_repair_id,
                )
                if hasattr(txn, "txn_time"):
                    txn.txn_time = when
                if hasattr(txn, "created_at"):
                    txn.created_at = when
                s.add(txn)
                s.flush()
            except Exception:
                # 4) 문제 발생 → 롤백되며 재고 변경도 취소됨. 재반영 + 안전 SQL로 이력 삽입
                s.rollback()

                c2 = s.get(Consumable, consumable_id)
                if c2 and hasattr(c2, "stock_qty") and proposed is not None:
                    setattr(c2, "stock_qty", proposed)
                    s.flush()

                _insert_txn_safe(
                    s,
                    consumable_id=getattr(c2 or c, "id", consumable_id),
                    qty=float(qty),
                    reason=(reason or None),
                    related_repair_id=related_repair_id,
                    when_dt=when,
                )
                txn = None
        else:
            # ORM 모델이 없으면: 재고 적용(가능 시) + 안전 SQL만 시도
            _insert_txn_safe(
                s,
                consumable_id=getattr(c, "id", consumable_id),
                qty=float(qty),
                reason=(reason or None),
                related_repair_id=related_repair_id,
                when_dt=when,
            )
            txn = None

        s.flush()
        return c, txn

def zero_out_stock(consumable_id: int, reason: str = "재고정리(0으로)") -> Tuple[Optional[Consumable], Optional[object]]:
    """
    ✅ 위와 동일 로직: ORM이 있으면 우선 사용,
       실패하거나 ORM이 없으면 안전 SQL로만 기록.
    """
    from datetime import datetime as _dt
    with session_scope() as s:
        c = s.get(Consumable, consumable_id)
        if not c:
            raise ValueError("해당 소모품이 없습니다.")
        if not hasattr(c, "stock_qty"):
            # 재고 컬럼이 없다면 아무 것도 하지 않음
            return c, None

        cur = float(getattr(c, "stock_qty", 0.0) or 0.0)
        if _is_zero(cur):
            return c, None

        delta = -cur  # 전량 출고로 0으로
        when = _dt.now()

        # 먼저 0으로 맞춤
        setattr(c, "stock_qty", 0.0)

        txn = None
        if HAS_TXN:
            try:
                txn = ConsumableTxn(
                    consumable_id=getattr(c, "id", consumable_id),
                    qty=delta,
                    reason=reason or None,
                    related_repair_id=None,
                )
                if hasattr(txn, "txn_time"):
                    txn.txn_time = when
                if hasattr(txn, "created_at"):
                    txn.created_at = when
                s.add(txn)
                s.flush()
            except Exception:
                s.rollback()

                c2 = s.get(Consumable, consumable_id)
                if c2 and hasattr(c2, "stock_qty"):
                    setattr(c2, "stock_qty", 0.0)
                    s.flush()

                _insert_txn_safe(
                    s, consumable_id=getattr(c2 or c, "id", consumable_id), qty=float(delta),
                    reason=(reason or None), related_repair_id=None, when_dt=when
                )
                txn = None
        else:
            _insert_txn_safe(
                s, consumable_id=getattr(c, "id", consumable_id), qty=float(delta),
                reason=(reason or None), related_repair_id=None, when_dt=when
            )
            txn = None

        s.flush()
        return c, txn

def low_stock_items() -> list[SimpleNamespace]:
    """
    안전수량(min_qty) 대비 부족한 품목만 DTO로 반환.
    min_qty 컬럼이 없으면 항상 0으로 간주(즉, 부족 없음).
    """
    items = list_consumables("")
    return [x for x in items if float(getattr(x, "min_qty", 0.0) or 0.0) > float(getattr(x, "stock_qty", 0.0) or 0.0)]

# ─────────────────────────────────────────────────────────────
# 정리/내보내기/양식
def clean_empty_consumables(force: bool = False) -> int:
    removed = 0
    with session_scope() as s:
        rows = s.execute(select(Consumable).order_by(Consumable.id.asc())).scalars().all()
        for c in rows:
            nm = (getattr(c, "name", "") or "").strip()
            if nm != "":
                continue

            has_txn = False
            if HAS_TXN:
                has_txn = s.execute(select(ConsumableTxn.id).where(ConsumableTxn.consumable_id == getattr(c, "id", -1))).first() is not None

            if has_txn and not force:
                continue
            if has_txn and force:
                s.execute(delete(ConsumableTxn).where(ConsumableTxn.consumable_id == getattr(c, "id", -1)))

            s.execute(delete(Consumable).where(Consumable.id == getattr(c, "id", -1)))
            removed += 1
    return removed

def export_consumables_xlsx(path: str | None = None) -> str:
    rows = []
    for c in list_consumables(""):
        rows.append({
            "ID": c.id,
            "품목": c.name or "",
            "규격": c.spec or "",
            "현재고": float(getattr(c, "stock_qty", 0.0) or 0.0),
            "안전수량": float(getattr(c, "min_qty", 0.0) or 0.0),
            "비고": getattr(c, "note", "") or "",
        })
    df = pd.DataFrame(rows, columns=["ID", "품목", "규격", "현재고", "안전수량", "비고"])
    if path is None:
        path = os.path.join(EXPORT_DIR, "소모품_내보내기.xlsx")
    df.to_excel(path, index=False)
    return path

def save_consumable_template_xlsx(path: str | None = None) -> str:
    df = pd.DataFrame([{
        "품목": "예) PLC퓨즈",
        "규격": "예) 2A/250V",
        "현재고": 0,
        "안전수량": 5,
        "비고": "예) 제어반 전용"
    }], columns=["품목", "규격", "현재고", "안전수량", "비고"])
    if path is None:
        path = os.path.join(TEMPLATES_DIR, "소모품_양식.xlsx")
    df.to_excel(path, index=False)
    return path

def save_consumable_txn_template_xlsx(path: str | None = None) -> str:
    """
    ✅ 입출고 '샘플' 양식 저장 (가져오기용 템플릿)
    컬럼:
      - 거래일시(YYYY-MM-DD HH:MM 또는 YYYY-MM-DD)
      - 품목
      - 규격
      - 수량
      - 입출고(입고/출고)
      - 사유(선택)
      - 관련 수리ID(선택)
    """
    cols = ["거래일시", "품목", "규격", "수량", "입출고", "사유", "관련 수리ID"]
    sample = [{
        "거래일시": "2025-01-01 09:00",
        "품목": "PLC퓨즈",
        "규격": "2A/250V",
        "수량": 10,
        "입출고": "입고",
        "사유": "초기 재고 등록",
        "관련 수리ID": "",
    },{
        "거래일시": "2025-01-03",
        "품목": "PLC퓨즈",
        "규격": "2A/250V",
        "수량": 2,
        "입출고": "출고",
        "사유": "라인 A 수리",
        "관련 수리ID": "",
    }]
    df = pd.DataFrame(sample, columns=cols)
    if path is None:
        path = os.path.join(TEMPLATES_DIR, "소모품_입출고_샘플.xlsx")
    df.to_excel(path, index=False)
    return path
