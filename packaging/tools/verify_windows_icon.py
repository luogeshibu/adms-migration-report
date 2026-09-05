from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True)
    args = parser.parse_args()
    exe = Path(args.exe).resolve()
    if not exe.is_file():
        raise SystemExit(f"EXE not found: {exe}")
    if os.name != "nt":
        raise SystemExit("Windows is required for EXE icon verification.")

    shell32 = ctypes.windll.shell32
    shell32.ExtractIconExW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    shell32.ExtractIconExW.restype = ctypes.c_uint
    count = shell32.ExtractIconExW(str(exe), -1, None, None, 0)
    if count < 1:
        raise SystemExit(f"No icon resource embedded in {exe.name}")
    print(f"Embedded EXE icon resources: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
