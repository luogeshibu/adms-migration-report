"""Source checkout launcher. Formal releases start MigrationReportTool.exe."""
from pathlib import Path
import multiprocessing
import sys
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from migration_report_tool.app.application import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
