from __future__ import annotations
import os, zipfile, datetime

# 제외 대상
EXCLUDE_DIRS  = {
    ".git", ".venv", "dist", "build", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".idea", ".vscode", "backups"  # ← 결과물이 들어갈 폴더, 반드시 제외!
}
EXCLUDE_FILES = {"app.db", "app.log"}
EXCLUDE_EXTS  = {".pyc", ".pyo", ".pyd", ".exe", ".dll", ".spec", ".so", ".zip"}  # 과거 백업 zip 재포함 방지

OUTPUT_PATH: str | None = None  # 자기 자신(출력 파일) 스킵용

def should_skip(rel_path: str, full_path: str) -> bool:
    """백업에서 제외할지 여부 판단."""
    # 0) 자기 자신(출력 파일) 제외
    try:
        if OUTPUT_PATH and os.path.exists(full_path) and os.path.exists(OUTPUT_PATH):
            # 같은 파일이면 스킵
            if os.path.samefile(full_path, OUTPUT_PATH):
                return True
    except Exception:
        # samefile 실패 시에도 계속 진행
        pass

    # 1) 디렉토리 제외 (경로 분해로 상위 디렉토리까지 체크)
    parts = rel_path.replace("\\", "/").split("/")
    for d in parts[:-1]:
        if d in EXCLUDE_DIRS:
            return True

    # 2) 파일명/확장자 제외
    base = os.path.basename(rel_path)
    if base in EXCLUDE_FILES:
        return True
    _, ext = os.path.splitext(base)
    if ext.lower() in EXCLUDE_EXTS:
        return True

    return False

def main():
    root = os.path.abspath(".")
    # 결과물을 별도 폴더에 생성 (자기포함 방지)
    backups_dir = os.path.join(root, "backups")
    os.makedirs(backups_dir, exist_ok=True)

    ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(backups_dir, f"backup_{ts}.zip")

    global OUTPUT_PATH
    OUTPUT_PATH = out  # should_skip에서 자기 자신 스킵 판단에 사용

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(root):
            # 디렉토리 필터 (하위 탐색 자체를 막음)
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

            for fn in filenames:
                full = os.path.join(dirpath, fn)
                rel  = os.path.relpath(full, root)
                if should_skip(rel, full):
                    continue
                zf.write(full, rel)

    size = os.path.getsize(out)
    print(f"✅ 백업 파일 생성: {out}  ({size:,} bytes)")

if __name__ == "__main__":
    main()
