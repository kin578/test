from __future__ import annotations
from typing import Optional, List
from PySide6.QtWidgets import QWidget, QLineEdit, QLabel

import user_session

# 객체명/placeholder/라벨 텍스트에서 탐지할 후보들
CANDIDATE_NAMES = [
    "vendor", "ed_vendor", "txt_vendor", "in_vendor",
    "writer", "ed_writer", "operator", "ed_operator",
    "responsible", "owner", "person", "contact",
]
CANDIDATE_LABELS = [
    "수리처", "수리처(이름)", "담당자", "작성자", "작업자", "Operator", "Vendor", "담당", "성명",
]

def _lineedits(root: QWidget) -> List[QLineEdit]:
    return root.findChildren(QLineEdit)

def _label_left_of(le: QLineEdit) -> str:
    # 같은 부모 위젯의 QLabel 중, 입력칸 왼쪽에 붙어있는 라벨 텍스트를 추정
    parent = le.parent()
    if not isinstance(parent, QWidget):
        return ""
    best = ""
    try:
        ly = le.geometry().center().y()
        lx = le.geometry().left()
        for w in parent.findChildren(QLabel):
            g = w.geometry()
            # 라벨이 왼쪽에 있고 수직 정렬이 비슷하면 후보
            if g.right() <= lx + 8 and abs(g.center().y() - ly) < 18:
                best = (w.text() or "").strip()
    except Exception:
        pass
    return best

def _is_target(le: QLineEdit) -> bool:
    obj = (le.objectName() or "").lower()
    if any(k in obj for k in CANDIDATE_NAMES):
        return True
    ph = (le.placeholderText() or "").strip()
    if ph and any(k in ph for k in (CANDIDATE_LABELS + ["이름", "담당"])):
        return True
    lbl = _label_left_of(le)
    if lbl and any(k in lbl for k in CANDIDATE_LABELS):
        return True
    return False

def apply_to_widget(root: QWidget) -> int:
    """
    로그인 사용자 이름을, '수리처/담당자/작성자'류 입력칸에
    **비어있을 때만** 채운다. 채운 항목 수를 반환.
    """
    cu = user_session.get_current_user()
    if not cu:
        return 0
    who = cu.name

    count = 0
    for le in _lineedits(root):
        if not _is_target(le):
            continue
        if not (le.text() or "").strip():
            le.setText(who)
            try:
                le.setCursorPosition(len(who))
            except Exception:
                pass
            count += 1
    return count
