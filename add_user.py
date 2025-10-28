from __future__ import annotations
import os, sys
from getpass import getpass

# 스크립트 위치를 작업폴더로 고정
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    # 내가 만들어둔 인증 서비스 사용
    from services.auth_service import add_user, list_users, ensure_default_admin
except Exception as e:
    print("services.auth_service 모듈을 찾을 수 없습니다. 프로젝트 루트에서 실행했는지 확인하세요.")
    print("에러:", e)
    sys.exit(1)

def main():
    # 기본 admin/1234 한 번 보장
    try:
        ensure_default_admin()
    except Exception:
        pass

    try:
        before = set(list_users())
    except Exception:
        before = set()

    print("=== 사용자 추가 ===")
    if before:
        print("현재 사용자:", ", ".join(sorted(before)))
    else:
        print("현재 사용자: (없음)")

    name = (input("새 사용자 이름: ") or "").strip()
    if not name:
        print("이름이 비었습니다. 종료합니다.")
        return

    pw1 = getpass("비밀번호 입력: ")
    pw2 = getpass("비밀번호 다시: ")
    if pw1 != pw2:
        print("비밀번호가 일치하지 않습니다. 종료합니다.")
        return

    role = (input("역할(user/admin) [user]: ") or "user").strip().lower()
    if role not in ("user", "admin"):
        role = "user"

    # 추가
    add_user(name, pw1, role=role)

    # 결과 안내
    after = set(list_users())
    if name in after and len(after) >= len(before):
        print(f"추가 완료! 사용자: {name} (role={role})")
    else:
        print("이미 존재하는 이름이거나 추가에 실패했습니다. 같은 이름이 있는지 확인하세요.")

    # users.json 위치 안내
    try:
        import settings
        try:
            root = settings.get_server_db_root()
        except Exception:
            root = os.path.abspath(".")
    except Exception:
        root = os.path.abspath(".")
    print(f"계정 파일(users.json): {os.path.join(root, 'users.json')}")

if __name__ == "__main__":
    main()
