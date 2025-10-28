from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass
class CurrentUser:
    name: str
    role: str = "user"

_current: Optional[CurrentUser] = None

def set_current_user(name: str, role: str = "user"):
    global _current
    _current = CurrentUser(name=name, role=role)

def get_current_user() -> Optional[CurrentUser]:
    return _current
