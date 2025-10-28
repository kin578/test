from __future__ import annotations
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Date, DateTime, ForeignKey, Text, Float, UniqueConstraint
from sqlalchemy import text

from db import Base, engine

# ─────────────────────────────────────────────────────────────────────
# 설비(Equipment)
class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 기본
    no: Mapped[Optional[int]] = mapped_column(Integer)                         # NO
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)     # 설비번호
    asset_name: Mapped[Optional[str]] = mapped_column(String(200))             # 자산명
    name: Mapped[str] = mapped_column(String(200), index=True)                 # 설비명
    alt_name: Mapped[Optional[str]] = mapped_column(String(200))               # 설비명 변경안
    model: Mapped[Optional[str]] = mapped_column(String(100))                  # 모델명

    # 스펙
    size_mm: Mapped[Optional[str]] = mapped_column(String(200))                # 크기(가로x세로x높이)mm
    voltage: Mapped[Optional[str]] = mapped_column(String(50))                 # 전압
    power_kwh: Mapped[Optional[float]] = mapped_column(Float)                  # 전력용량(Kwh)

    util_air: Mapped[Optional[str]] = mapped_column(String(200))               # 유틸리티 AIR
    util_coolant: Mapped[Optional[str]] = mapped_column(String(200))           # 유틸리티 냉각수
    util_vac: Mapped[Optional[str]] = mapped_column(String(200))               # 유틸리티 진공
    util_other: Mapped[Optional[str]] = mapped_column(String(200))             # 유틸리티 기타
    purpose: Mapped[Optional[str]] = mapped_column(String(200))                # ★ 용도(신규)

    # 제조/입고
    maker: Mapped[Optional[str]] = mapped_column(String(100))                  # 제조회사
    maker_phone: Mapped[Optional[str]] = mapped_column(String(50))             # 제조회사 대표 전화번호
    manufacture_date: Mapped[Optional[date]] = mapped_column(Date)             # 제조일자

    in_year: Mapped[Optional[int]] = mapped_column(Integer)                    # 입고일(년)
    in_month: Mapped[Optional[int]] = mapped_column(Integer)                   # 입고일(월)
    in_day: Mapped[Optional[int]] = mapped_column(Integer)                     # 입고일(일)

    qty: Mapped[Optional[float]] = mapped_column(Float)                        # 수량
    purchase_price: Mapped[Optional[float]] = mapped_column(Float)             # 구입가격
    location: Mapped[Optional[str]] = mapped_column(String(200))               # 설비위치
    note: Mapped[Optional[str]] = mapped_column(Text)                          # 비고
    part: Mapped[Optional[str]] = mapped_column(String(100))                   # 파트
    installed_on: Mapped[Optional[date]] = mapped_column(Date)                 # 설치일 (선택)

    # 상태/분류/삭제 표식
    status: Mapped[Optional[str]] = mapped_column(String(20))                  # 가동/유휴/매각/이전
    category: Mapped[Optional[str]] = mapped_column(String(100))               # 카테고리(선택)
    is_deleted: Mapped[int] = mapped_column(Integer, default=0)                # 보관함 이동(1) / 정상(0)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)           # 삭제 일시(soft)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 관계
    photos: Mapped[List["Photo"]] = relationship(back_populates="equipment", cascade="all, delete-orphan")
    repairs: Mapped[List["Repair"]] = relationship(back_populates="equipment", cascade="all, delete-orphan")
    accessories: Mapped[List["EquipmentAccessory"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan", order_by="EquipmentAccessory.ord"
    )

# ─────────────────────────────────────────────────────────────────────
# 설비 사진
class Photo(Base):
    __tablename__ = "photo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    equipment_code: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    # 과거/현재 호환을 위해 둘 다 둠. 파일 저장 시 둘 다 세팅.
    path: Mapped[Optional[str]] = mapped_column(String(500))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))

    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    equipment: Mapped["Equipment"] = relationship(back_populates="photos")

# ─────────────────────────────────────────────────────────────────────
class Repair(Base):
    __tablename__ = "repair"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)

    kind: Mapped[str] = mapped_column(String(50))                               # 수리/개선/점검
    title: Mapped[str] = mapped_column(String(200))                             # 현황 파악
    detail: Mapped[Optional[str]] = mapped_column(Text)                         # 개선 및 수리 내용

    # 추가 컬럼
    vendor: Mapped[Optional[str]] = mapped_column(String(100))                  # 수리처
    work_hours: Mapped[Optional[float]] = mapped_column(Float)                  # 수리 시간
    progress_status: Mapped[Optional[str]] = mapped_column(String(20))          # 진행상태
    complete_date: Mapped[Optional[date]] = mapped_column(Date)                 # 완료 일자

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    equipment: Mapped["Equipment"] = relationship(back_populates="repairs")
    items: Mapped[List["RepairItem"]] = relationship(back_populates="repair", cascade="all, delete-orphan")
    photos: Mapped[List["RepairPhoto"]] = relationship(back_populates="repair", cascade="all, delete-orphan")

# ─────────────────────────────────────────────────────────────────────
class Consumable(Base):
    __tablename__ = "consumable"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    spec: Mapped[Optional[str]] = mapped_column(String(200))
    stock_qty: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[Optional[str]] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("name", "spec", name="uq_consumable_name_spec"),)

# ─────────────────────────────────────────────────────────────────────
class RepairItem(Base):
    __tablename__ = "repair_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repair_id: Mapped[int] = mapped_column(ForeignKey("repair.id", ondelete="CASCADE"), index=True)
    consumable_id: Mapped[int] = mapped_column(ForeignKey("consumable.id", ondelete="RESTRICT"), index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)

    repair: Mapped["Repair"] = relationship(back_populates="items")
    consumable: Mapped["Consumable"] = relationship()

# ─────────────────────────────────────────────────────────────────────
class RepairPhoto(Base):
    __tablename__ = "repair_photo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    repair_id: Mapped[int] = mapped_column(ForeignKey("repair.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    shot_at: Mapped[Optional[date]] = mapped_column(Date)

    repair: Mapped["Repair"] = relationship(back_populates="photos")

# ─────────────────────────────────────────────────────────────────────
class EquipmentAccessory(Base):
    __tablename__ = "equipment_accessory"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), index=True)
    ord: Mapped[int] = mapped_column(Integer, default=0)                        # 표시 순서
    name: Mapped[str] = mapped_column(String(200))                              # 품명
    spec: Mapped[Optional[str]] = mapped_column(String(200))                    # 규격
    note: Mapped[Optional[str]] = mapped_column(String(200))                    # 비고

    equipment: Mapped["Equipment"] = relationship(back_populates="accessories")

# ─────────────────────────────────────────────────────────────────────
# ★ 변경 이력(ChangeLog)
class ChangeLog(Base):
    __tablename__ = "change_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(String(50), index=True)     # 'equipment' / 'repair'
    record_id: Mapped[int] = mapped_column(Integer, index=True)
    field: Mapped[str] = mapped_column(String(100))
    before: Mapped[Optional[str]] = mapped_column(Text)
    after: Mapped[Optional[str]] = mapped_column(Text)
    user: Mapped[Optional[str]] = mapped_column(String(100))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ─────────────────────────────────────────────────────────────────────
# DB 초기화 + 경량 마이그레이션
def init_db():
    """테이블 생성 + 누락 컬럼 보강(기존 DB 안전 유지)."""
    Base.metadata.create_all(engine)

    # equipment 컬럼 보강
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(equipment)")).fetchall()}
        def add(sql: str): conn.execute(text(sql))

        wanted = {
            "no": "ALTER TABLE equipment ADD COLUMN no INTEGER",
            "asset_name": "ALTER TABLE equipment ADD COLUMN asset_name VARCHAR(200)",
            "alt_name": "ALTER TABLE equipment ADD COLUMN alt_name VARCHAR(200)",
            "size_mm": "ALTER TABLE equipment ADD COLUMN size_mm VARCHAR(200)",
            "voltage": "ALTER TABLE equipment ADD COLUMN voltage VARCHAR(50)",
            "power_kwh": "ALTER TABLE equipment ADD COLUMN power_kwh FLOAT",
            "util_air": "ALTER TABLE equipment ADD COLUMN util_air VARCHAR(200)",
            "util_coolant": "ALTER TABLE equipment ADD COLUMN util_coolant VARCHAR(200)",
            "util_vac": "ALTER TABLE equipment ADD COLUMN util_vac VARCHAR(200)",
            "util_other": "ALTER TABLE equipment ADD COLUMN util_other VARCHAR(200)",
            "purpose": "ALTER TABLE equipment ADD COLUMN purpose VARCHAR(200)",  # ★ 추가
            "maker": "ALTER TABLE equipment ADD COLUMN maker VARCHAR(100)",
            "maker_phone": "ALTER TABLE equipment ADD COLUMN maker_phone VARCHAR(50)",
            "manufacture_date": "ALTER TABLE equipment ADD COLUMN manufacture_date DATE",
            "in_year": "ALTER TABLE equipment ADD COLUMN in_year INTEGER",
            "in_month": "ALTER TABLE equipment ADD COLUMN in_month INTEGER",
            "in_day": "ALTER TABLE equipment ADD COLUMN in_day INTEGER",
            "qty": "ALTER TABLE equipment ADD COLUMN qty FLOAT",
            "purchase_price": "ALTER TABLE equipment ADD COLUMN purchase_price FLOAT",
            "location": "ALTER TABLE equipment ADD COLUMN location VARCHAR(200)",
            "note": "ALTER TABLE equipment ADD COLUMN note TEXT",
            "part": "ALTER TABLE equipment ADD COLUMN part VARCHAR(100)",
            "installed_on": "ALTER TABLE equipment ADD COLUMN installed_on DATE",
            "status": "ALTER TABLE equipment ADD COLUMN status VARCHAR(20)",
            "category": "ALTER TABLE equipment ADD COLUMN category VARCHAR(100)",
            "is_deleted": "ALTER TABLE equipment ADD COLUMN is_deleted INTEGER DEFAULT 0",
            "deleted_at": "ALTER TABLE equipment ADD COLUMN deleted_at DATETIME",
        }
        for c, sql in wanted.items():
            if c not in cols: add(sql)

    # repair 컬럼 보강
    with engine.connect() as conn:
        rcols = {row[1] for row in conn.execute(text("PRAGMA table_info(repair)")).fetchall()}
        def add(sql: str): conn.execute(text(sql))
        needed = {
            "progress_status": "ALTER TABLE repair ADD COLUMN progress_status VARCHAR(20)",
            "complete_date":  "ALTER TABLE repair ADD COLUMN complete_date DATE",
            "vendor":         "ALTER TABLE repair ADD COLUMN vendor VARCHAR(100)",
            "work_hours":     "ALTER TABLE repair ADD COLUMN work_hours FLOAT",
        }
        for c, sql in needed.items():
            if c not in rcols: add(sql)

    # photo 컬럼 보강(file_path)
    with engine.connect() as conn:
        pcols = {row[1] for row in conn.execute(text("PRAGMA table_info(photo)")).fetchall()}
        if "file_path" not in pcols:
            conn.execute(text("ALTER TABLE photo ADD COLUMN file_path VARCHAR(500)"))

    Base.metadata.create_all(engine)
