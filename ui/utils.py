from __future__ import annotations
from datetime import date, datetime
import os, re

def fmt_kr_price(n) -> str:
    if n is None or n == "": 
        return ""
    try:
        return f"₩{float(n):,.0f}"
    except Exception:
        return str(n)

def fmt_kr_date(y: int | None, m: int | None, d: int | None) -> str:
    if y:
        return f"{y}년 {m or 1}월 {d or 1}일"
    return ""

def to_text_date(x) -> str:
    if x is None: 
        return ""
    if isinstance(x, (date, datetime)): 
        return x.strftime("%Y-%m-%d")
    return str(x)

def parse_date_smart(s: str):
    s = (s or "").strip()
    if not s: 
        return None
    for fmt in ("%Y-%m-%d","%Y.%m.%d","%Y/%m/%d","%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    m = re.match(r"^\s*(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*$", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            return None
    return None

def is_image_file(path: str) -> bool:
    return path.lower().endswith((".png",".jpg",".jpeg",".bmp",".gif",".webp"))

def clear_all_images(folder: str):
    if not os.path.isdir(folder): 
        return
    for fn in os.listdir(folder):
        if is_image_file(fn):
            try:
                os.remove(os.path.join(folder, fn))
            except Exception:
                pass

def project_root_from(file_path: str) -> str:
    """ui/tabs/... 같은 위치에서 프로젝트 루트 상대경로 계산"""
    return os.path.abspath(os.path.join(os.path.dirname(file_path), "../.."))
