"""Source checkout launcher. Formal releases start MigrationReportTool.exe."""
from pathlib import Path
import multiprocessing
import sys


def packaged_self_test() -> int:
    """Validate a frozen bundle without importing Qt or opening a window."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    required = (
        bundle_root / "assets" / "logo.ico",
        bundle_root / "assets" / "logo.png",
        bundle_root / "templates" / "IOA STANDARD.xlsx",
        bundle_root / "icons" / "rmu.svg",
        bundle_root / "icons" / "signal.svg",
    )
    return 0 if all(path.is_file() for path in required) else 2


# The formal Windows build calls the EXE with --self-test. Keep that path
# dependency-light so a missing Qt runtime cannot turn a validation check into
# a hidden GUI process that locks the staging directory.
if "--self-test" in sys.argv:
    raise SystemExit(packaged_self_test())

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

def _is_multiprocessing_child() -> bool:
    """Prevent Windows spawn workers from launching the desktop UI again."""
    try:
        return (
            multiprocessing.parent_process() is not None
            or multiprocessing.current_process().name != "MainProcess"
        )
    except Exception:
        return False


if __name__ == "__main__" and not _is_multiprocessing_child():
    from migration_report_tool.app.application import main
    multiprocessing.freeze_support()
    raise SystemExit(main())
