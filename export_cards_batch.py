# D:\equipment_manager_app\export_cards_batch.py
from __future__ import annotations
from services.export_history_card import export_history_cards_multi_xlsx

# ① 내보낼 설비 코드 목록(설비관리대장 첫 열의 코드들)
EQUIPMENT_CODES = [
    "DS-PT-02-189",
    "DS-PT-B1-012",
    # 필요하면 계속 추가
]

# ② 저장 경로(비워두면 D:\equipment_manager_app\exports\ 로 자동 저장)
OUT_PATH = r""  # 예: r"C:\Users\내이름\Desktop\이력카드_묶음.xlsx"

# ③ 정렬 기준: "code" 또는 "name"
SORT_BY = "name"   # 코드순 원하면 "code"

# ④ 시트 이름 규칙: {code}, {name} 사용 가능
SHEET_TITLE_FORMAT = "{code} - {name}"  # 예: "{name}", "이력카드-{name}" 등

def main():
    out = export_history_cards_multi_xlsx(
        equipment_codes=EQUIPMENT_CODES,
        path=OUT_PATH or None,          # 비우면 exports 폴더에 자동 저장
        template_path=None,             # 기본 이력카드 템플릿 사용
        fill_machine_no=False,          # 기기번호 칸까지 넣고 싶으면 True
        sort_by=SORT_BY,                # "code" or "name"
        sheet_title_format=SHEET_TITLE_FORMAT,
    )
    print("완료:", out)

if __name__ == "__main__":
    main()
