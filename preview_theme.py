# preview_theme.py
# 테마 미리보기(앱 통합 전, 단독 실행용)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit, QTextEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox, QLabel
)
from PySide6.QtCore import Qt
from lux_theme import apply_theme


def build_demo_window():
    w = QWidget()
    w.setWindowTitle("테마 미리보기")

    root = QVBoxLayout(w)

    # 상단 컨트롤
    box = QGroupBox("폼 컨트롤")
    lay = QVBoxLayout(box)

    row1 = QHBoxLayout()
    row1.addWidget(QLabel("이름"))
    row1.addWidget(QLineEdit(placeholderText="이름을 입력하세요"))
    row1.addWidget(QLabel("수량"))
    sp = QSpinBox(); sp.setMaximum(9999); sp.setValue(3); row1.addWidget(sp)
    row1.addWidget(QLabel("상태"))
    cb = QComboBox(); cb.addItems(["가동","유휴","매각","이전"]); row1.addWidget(cb)
    row1.addStretch(1)
    lay.addLayout(row1)

    memo = QTextEdit(); memo.setPlaceholderText("메모/특이사항…")
    lay.addWidget(memo)
    root.addWidget(box)

    # 버튼 영역
    btns = QHBoxLayout()
    b1 = QPushButton("기본"); b2 = QPushButton("확인"); b3 = QPushButton("삭제")
    b2.setProperty("primary", True); b3.setProperty("danger", True)
    btns.addWidget(b1); btns.addWidget(b2); btns.addWidget(b3); btns.addStretch(1)
    root.addLayout(btns)

    # 테이블
    tbl = QTableWidget(5, 4)
    tbl.setHorizontalHeaderLabels(["설비번호","설비명","상태","체크"])
    for r in range(5):
        for c in range(3):
            tbl.setItem(r, c, QTableWidgetItem(f"R{r+1}C{c+1}"))
        chk = QCheckBox(); tbl.setCellWidget(r, 3, chk)
    root.addWidget(tbl)

    return w


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)

    # 👇 여기서 다크/라이트와 포인트 색을 바꿔가며 테스트
    apply_theme(app, mode="dark", accent="#4f46e5", corner_radius=12)

    win = build_demo_window()
    win.resize(900, 600)
    win.show()
    sys.exit(app.exec())
