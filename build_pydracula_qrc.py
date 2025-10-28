from __future__ import annotations
import os, xml.etree.ElementTree as ET

BASE = "vendor/pydracula"
IMAGES_DIR = os.path.join(BASE, "images")           # 아이콘/이미지 폴더
QRC_PATH   = os.path.join(BASE, "resources.qrc")    # 생성될 qrc

VALID_EXT = {".png",".jpg",".jpeg",".bmp",".gif",".svg",".ico"}

def list_files(root_dir: str):
    files = []
    for r, _, fns in os.walk(root_dir):
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext in VALID_EXT:
                full = os.path.join(r, fn)
                rel = os.path.relpath(full, BASE).replace("\\","/")  # 예: images/icons/home.svg
                if rel.startswith("images/"):
                    files.append(rel)
    files.sort()
    return files

def build_qrc(files: list[str], qrc_path: str):
    # QSS에서 보통 url(:/icons/... 또는 :/images/...) 를 쓰므로,
    # prefix="/"로 등록 + alias를 "icons/..."와 "images/..." 둘 다 대응되게 만듦
    rcc = ET.Element("RCC", version="1.0")
    qres = ET.SubElement(rcc, "qresource", prefix="/")

    for rel in files:
        # 예: images/icons/home.svg → 두 가지로 노출
        # 1) 그대로:   :/images/icons/home.svg
        f1 = ET.SubElement(qres, "file", alias=rel)
        f1.text = rel
        # 2) icons/ 접두사도 제공: :/icons/images/icons/home.svg (일부 QSS가 이렇게 씀)
        f2 = ET.SubElement(qres, "file", alias=f"icons/{rel}")
        f2.text = rel

    # pretty 출력
    xml = ET.tostring(rcc, encoding="utf-8")
    import xml.dom.minidom as md
    pretty = md.parseString(xml).toprettyxml(indent="  ", encoding="utf-8")
    os.makedirs(os.path.dirname(qrc_path), exist_ok=True)
    with open(qrc_path, "wb") as fp:
        fp.write(pretty)

def main():
    if not os.path.isdir(IMAGES_DIR):
        raise SystemExit(f"[오류] 이미지 폴더 없음: {IMAGES_DIR}")
    files = list_files(IMAGES_DIR)
    if not files:
        raise SystemExit(f"[오류] 이미지 파일이 없습니다: {IMAGES_DIR}")
    build_qrc(files, QRC_PATH)
    print(f"[완료] {QRC_PATH} 생성 (항목 {len(files)}개)")
    print("\n이제 아래 명령으로 컴파일하세요:")
    print("  python -m PySide6.scripts.pyside6-rcc vendor/pydracula/resources.qrc -o vendor/pydracula/modules/resources_rc.py")

if __name__ == "__main__":
    main()
