"""Optional Microsoft Excel calculation bridge for formula-backed review workbooks.

openpyxl preserves spreadsheet formulas but does not evaluate them.  On Windows
workstations that have Microsoft Excel installed, the application can ask Excel
itself to calculate a temporary workbook copy (for UI display) or the final
export workbook (for fresh cached formula results).  The source site workbook
is never modified by the temporary-copy workflow.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


@dataclass(frozen=True)
class ExcelCalculationStatus:
    success: bool
    mode: str
    message: str = ""


_POWERSHELL_SCRIPT = r'''
param([Parameter(Mandatory=$true)][string]$WorkbookPath)
$ErrorActionPreference = "Stop"
$excel = $null
$book = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.AskToUpdateLinks = $false
    $book = $excel.Workbooks.Open($WorkbookPath, 0, $false)
    # Full rebuild is used rather than Calculate so dependency chains that were
    # changed by the migration export (for example DATA -> RMU Data Review)
    # are recalculated from scratch.
    $excel.CalculateFullRebuild()
    $book.Save()
    $book.Close($true)
    $book = $null
}
finally {
    if ($book -ne $null) {
        try { $book.Close($false) } catch {}
    }
    if ($excel -ne $null) {
        try { $excel.Quit() } catch {}
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel) } catch {}
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
'''


def recalculate_workbook_in_place(path: Path, timeout_seconds: int = 120) -> ExcelCalculationStatus:
    """Ask desktop Excel to fully calculate and save ``path``.

    This is best-effort.  It intentionally has no pywin32 dependency so the
    same application package remains portable; Windows PowerShell supplies the
    COM bridge.  On non-Windows systems, or if Excel is not installed, callers
    receive a normal fallback status and can continue using saved cache values.
    """
    path = Path(path).resolve()
    if os.name != "nt":
        return ExcelCalculationStatus(False, "cached-values", "Microsoft Excel recalculation is only available on Windows.")
    if not path.exists():
        return ExcelCalculationStatus(False, "cached-values", f"Workbook not found: {path}")

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        return ExcelCalculationStatus(False, "cached-values", "Windows PowerShell is not available.")

    script_file = None
    try:
        fd, script_name = tempfile.mkstemp(prefix="migration_excel_calc_", suffix=".ps1")
        os.close(fd)
        script_file = Path(script_name)
        script_file.write_text(_POWERSHELL_SCRIPT, encoding="utf-8-sig")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_file),
                "-WorkbookPath",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(15, int(timeout_seconds)),
            creationflags=flags,
            check=False,
        )
        if result.returncode == 0:
            return ExcelCalculationStatus(True, "excel-recalculated", "Formula values recalculated by Microsoft Excel.")
        detail = (result.stderr or result.stdout or "Excel automation failed.").strip()
        if len(detail) > 500:
            detail = detail[-500:]
        return ExcelCalculationStatus(False, "cached-values", detail)
    except subprocess.TimeoutExpired:
        return ExcelCalculationStatus(False, "cached-values", f"Excel recalculation exceeded {timeout_seconds} seconds.")
    except Exception as exc:
        return ExcelCalculationStatus(False, "cached-values", f"{type(exc).__name__}: {exc}")
    finally:
        if script_file:
            try:
                script_file.unlink(missing_ok=True)
            except Exception:
                pass


@contextmanager
def recalculated_workbook_copy(source: Path, timeout_seconds: int = 120):
    """Yield a recalculated temporary copy and its status.

    The source workbook remains untouched.  If Excel automation is unavailable,
    the original source path is yielded and callers can read its saved formula
    cache with ``data_only=True``.
    """
    source = Path(source).resolve()
    temp_dir = Path(tempfile.mkdtemp(prefix="migration_report_excel_"))
    copy_path = temp_dir / source.name
    try:
        shutil.copy2(source, copy_path)
        status = recalculate_workbook_in_place(copy_path, timeout_seconds=timeout_seconds)
        yield (copy_path if status.success else source), status
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
