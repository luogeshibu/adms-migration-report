from __future__ import annotations
import argparse, importlib, platform, struct, sys
from pathlib import Path

def fail(msg: str):
    print(f"[ERROR] {msg}")
    raise SystemExit(2)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    a = p.parse_args()
    root = Path(a.root).resolve()
    required = [
        root/'setup.bat', root/'build.ps1', root/'pyproject.toml', root/'requirements.lock.txt', root/'packaging/windows/MigrationReportTool.spec',
        root/'resources/assets/logo.ico', root/'resources/assets/logo.png',
        root/'resources/icons/rmu.svg', root/'resources/icons/signal.svg',
        root/'resources/templates/IOA STANDARD.xlsx',
        root/'src/migration_report_tool/app/application.py',
    ]
    missing = [str(x) for x in required if not x.exists()]
    if missing: fail('Missing required project files: ' + ', '.join(missing))
    if struct.calcsize('P') * 8 != 64: fail('64-bit Python is required for Windows x64 releases.')
    from migration_report_tool import __version__
    import PySide6, openpyxl, PyInstaller
    print(f"Version: {__version__}")
    print(f"Python: {platform.python_version()} ({struct.calcsize('P')*8}-bit)")
    print(f"PySide6: {PySide6.__version__}")
    print(f"openpyxl: {openpyxl.__version__}")
    print(f"PyInstaller: {PyInstaller.__version__}")
    print("Preflight: PASS")

if __name__ == '__main__': main()
