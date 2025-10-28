# deploy/build_onedir.py
import os, sys, subprocess, shutil, datetime
from pathlib import Path

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.check_call(cmd)

def ensure_pyinstaller(pyexe):
    try:
        __import__("PyInstaller")
        print("PyInstaller OK")
    except Exception:
        print("Installing PyInstaller...")
        run([pyexe, "-m", "pip", "install", "-U", "pyinstaller"])

def main():
    proj_root = Path(__file__).resolve().parents[1]
    pyexe = sys.executable  # 현재 venv 파이썬
    os.environ["EM_PROJROOT"] = str(proj_root)

    ensure_pyinstaller(pyexe)

    # Clean
    if "--clean" in sys.argv:
        for p in ["build", "dist", "__pycache__"]:
            pp = proj_root / p
            if pp.exists():
                print("rm -rf", pp)
                shutil.rmtree(pp)

    # spec 경로 선택 (deploy/app.spec → app.spec)
    spec = proj_root / "deploy" / "app.spec"
    if not spec.exists():
        spec = proj_root / "app.spec"
    if not spec.exists():
        print("Spec not found: deploy/app.spec or app.spec")
        sys.exit(1)

    # 빌드
    run([pyexe, "-m", "PyInstaller", "--clean", "-y", str(spec)])

    dist_dir = proj_root / "dist" / "설비관리프로그램"
    if not dist_dir.exists():
        print("Build failed: dist/설비관리프로그램 not found")
        sys.exit(1)

    print("Build done:", dist_dir)

    # ZIP 옵션
    if "--zip" in sys.argv:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_base = proj_root / "dist" / f"설비관리프로그램_{stamp}"
        # 폴더째로 압축 (zip 안에 '설비관리프로그램' 폴더가 보이도록)
        root_dir = dist_dir.parent       # dist
        base_dir = dist_dir.name         # 설비관리프로그램
        shutil.make_archive(str(zip_base), "zip", root_dir=str(root_dir), base_dir=str(base_dir))
        print("ZIP created:", str(zip_base) + ".zip")

if __name__ == "__main__":
    main()
