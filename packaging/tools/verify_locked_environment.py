from __future__ import annotations

import argparse
import importlib.metadata
import re
import sys
from pathlib import Path

LOCK_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)==([^\s;#]+)\s*$")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify installed packages against requirements.lock.txt")
    parser.add_argument("--lock", required=True, type=Path)
    args = parser.parse_args()

    expected: dict[str, tuple[str, str]] = {}
    for line in args.lock.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_RE.match(line)
        if not match:
            print(f"ERROR: unsupported/unlocked requirement in {args.lock}: {line}", file=sys.stderr)
            return 2
        dist_name, version = match.groups()
        expected[normalize(dist_name)] = (dist_name, version)

    errors: list[str] = []
    for _normalized, (dist_name, required_version) in sorted(expected.items()):
        try:
            installed = importlib.metadata.version(dist_name)
        except importlib.metadata.PackageNotFoundError:
            errors.append(f"{dist_name}: required {required_version}, not installed")
            continue
        if installed != required_version:
            errors.append(f"{dist_name}: required {required_version}, installed {installed}")
        else:
            print(f"OK  {dist_name}=={installed}")

    if errors:
        print("\nLocked dependency validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("Run setup.bat to synchronize the Windows environment.", file=sys.stderr)
        return 1

    print(f"Locked dependency validation passed ({len(expected)} packages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
