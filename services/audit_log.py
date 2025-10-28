from __future__ import annotations
import os, sys
from datetime import datetime
from typing import Optional

try:
    import settings
    LOG_DIR = os.path.join(settings.get_server_db_root(), "logs")  # 서버 쪽에 보관
except Exception:
    LOG_DIR = os.path.abspath("./logs")

os.makedirs(LOG_DIR, exist_ok=True)

def _log_path() -> str:
    return os.path.join(LOG_DIR, f"app_{datetime.now():%Y%m%d}.log")

def log_event(action: str, detail: str = "", user: Optional[str] = None) -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        who = user or "-"
        line = f"{ts}\t{who}\t{action}\t{detail}\n"
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
