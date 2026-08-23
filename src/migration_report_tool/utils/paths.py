"""Application, resource, workspace and user-reference path policy."""
from pathlib import Path
import os
import sys


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # source layout: <root>/src/migration_report_tool/utils/paths.py
    return Path(__file__).resolve().parents[3]


def resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return app_root() / "resources"


def workspace_root() -> Path:
    root = app_root() / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def is_inside_workspace(path: Path) -> bool:
    try:
        path.resolve().relative_to(workspace_root().resolve())
        return True
    except ValueError:
        return False


def user_data_root() -> Path:
    """Writable application-level data that must survive release replacement.

    On Windows application-global settings and the active STANDARD override are
    stored under LOCALAPPDATA rather than inside the packaged release folder.
    Tests/portable deployments may override the location with
    ``MIGRATION_REPORT_TOOL_USER_DATA_ROOT``.
    """
    explicit = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
    if explicit:
        return Path(explicit)
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "MigrationReportTool"
    return workspace_root() / ".app"


def bundled_standard_reference_path() -> Path:
    """Immutable STANDARD workbook shipped with the application release."""
    return resource_root() / "templates" / "IOA STANDARD.xlsx"


def standard_override_path() -> Path:
    """User-managed global STANDARD workbook, if one has been approved."""
    return user_data_root() / "reference" / "IOA STANDARD.xlsx"


def standard_reference_metadata_path() -> Path:
    return user_data_root() / "reference" / "standard_reference.json"


def standard_reference_path() -> Path:
    """Return the active STANDARD workbook used by review and export.

    Priority is explicit and deterministic:
      1. validated user override;
      2. bundled release reference.
    """
    override = standard_override_path()
    return override if override.exists() else bundled_standard_reference_path()


def standard_reference_origin() -> str:
    return "User Override" if standard_override_path().exists() else "Built-in"
