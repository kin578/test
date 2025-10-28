# list_tree.py
import os, sys

# ▶ 여기를 프로젝트 최상위 폴더 경로로 바꿔도 되고,
#   그냥 list_tree.py를 프로젝트 폴더에 두고 실행해도 됨.
ROOT = os.path.abspath(os.path.dirname(__file__))

# 너무 긴 목록 방지를 위한 제외 폴더(원하면 추가/삭제 가능)
EXCLUDE_DIRS = {'.git', '.idea', '.vscode', '__pycache__', 'venv', '.venv', 'node_modules', 'dist', 'build'}

out_lines = []
for base, dirs, files in os.walk(ROOT):
    # 제외 폴더 스킵
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    rel_base = os.path.relpath(base, ROOT)
    if rel_base == '.': rel_base = ''
    # 폴더 라인
    out_lines.append(f"[DIR] {rel_base or '/'}")
    # 파일 라인
    for f in sorted(files):
        p = os.path.join(base, f)
        rel = os.path.relpath(p, ROOT)
        size = os.path.getsize(p)
        out_lines.append(f"  - {rel} ({size} bytes)")
    out_lines.append("")

# 핵심 파일 빠르게 찾기(서비스/탭/내보내기 등)
KEYWORDS = ["export", "history_card", "repair", "equipment", "service", "tab"]
out_lines.append("# Quick search")
for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
    for f in files:
        if any(k in f.lower() for k in KEYWORDS):
            rel = os.path.relpath(os.path.join(base, f), ROOT)
            out_lines.append(f"  * {rel}")

# 결과 저장
out_path = os.path.join(ROOT, "project_tree.txt")
with open(out_path, "w", encoding="utf-8") as fw:
    fw.write("\n".join(out_lines))

print(f"완료! 파일 생성: {project_tree.txt}")
