"""Application, resource, persistent project-data and user-reference path policy."""
from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
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


def user_data_root() -> Path:
    """Writable application-level data that survives replacing the release folder."""
    explicit = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
    if explicit:
        root = Path(explicit).expanduser()
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"]) / "MigrationReportTool"
    else:
        root = Path.home() / ".migration-report-tool"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_data_config_path() -> Path:
    path = user_data_root() / "settings" / "project_data.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_project_data_config() -> dict:
    path = _project_data_config_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def configured_project_data_root() -> Path | None:
    """Return the explicitly selected Project Data path, if one exists.

    This deliberately does not create or rewrite the path.  Keeping the
    configured value separate from the safe fallback lets the application
    recover when a network share is temporarily offline without losing the
    original location.
    """
    explicit = os.environ.get("MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT")
    if explicit:
        return Path(explicit).expanduser()
    configured = str(_load_project_data_config().get("root", "") or "").strip()
    return Path(configured).expanduser() if configured else None


def _directory_is_available(path: Path) -> bool:
    try:
        return path.exists() and path.is_dir()
    except OSError:
        return False


def project_data_root_is_available() -> bool:
    """Whether the explicitly configured Project Data path can be opened."""
    configured = configured_project_data_root()
    if configured is None:
        return True
    return _directory_is_available(configured)


def project_data_root() -> Path:
    """Persistent root for all per-site project records.

    This path is deliberately independent from the source/EXE directory, so
    replacing or upgrading the application cannot remove Review, Closed,
    Needs Action, Comments, Resolution, Audit, source mappings or snapshots.
    """
    root = configured_project_data_root() or (user_data_root() / "project_data")
    # Never create a remembered UNC folder while the Qt window is being built.
    # A disconnected Windows share can make mkdir block for a long time.  The
    # path is kept unchanged and checked from a background startup task.
    if os.name == "nt" and str(root).startswith("\\\\"):
        return root
    try:
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        # A remembered UNC path can disappear when the server is stopped, the
        # network is disconnected, or credentials have expired.  Never let a
        # missing share prevent the UI from opening, and never replace the
        # remembered path.  The setup dialog will ask the user for a usable
        # location and the fallback is only a temporary local safety net.
        fallback = (user_data_root() / "project_data_offline").resolve()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback




def project_data_root_is_configured() -> bool:
    """Return True when Project Data is explicitly chosen and currently usable.

    New installs create the default folder lazily, so folder existence alone is
    not enough to consider setup complete. Existing upgrades that already have
    per-site project.db files are treated as established to avoid interrupting
    reviewers with a one-time migration prompt. A disconnected network path is
    intentionally reported as unconfigured so the UI can request a replacement.
    """
    configured = configured_project_data_root()
    if configured is not None:
        # UNC reachability is checked by the post-show startup worker. Do not
        # turn the first GUI event-loop turn into a network timeout.
        if os.name == "nt" and str(configured).startswith("\\\\"):
            return True
        return project_data_root_is_available()
    default_root = user_data_root() / "project_data"
    workspace = default_root / "workspace"
    if not workspace.exists():
        return False
    try:
        return any(workspace.glob("*/project.db"))
    except OSError:
        return False


def confirm_project_data_root(root: Path | None = None) -> Path:
    """Persist the current/default Project Data location as an explicit user choice."""
    return set_project_data_root(Path(root) if root is not None else project_data_root())

def set_project_data_root(root: Path) -> Path:
    """Persist the Project Data root used by this and future application versions."""
    target = Path(root).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    payload = _load_project_data_config()
    payload["root"] = str(target)
    _project_data_config_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def _adopt_legacy_release_workspace(target_workspace: Path) -> None:
    """One-time safe adoption of v0.8.42-style release-local site data.

    Existing persistent sites are never overwritten. This allows the first
    persistent build to carry forward site project.db files if the old release
    directory still contains them, while all future versions use Project Data.
    """
    marker = user_data_root() / "settings" / "legacy_workspace_adopted_v1"
    if marker.exists():
        return
    legacy = app_root() / "workspace"
    try:
        same = legacy.resolve() == target_workspace.resolve()
    except OSError:
        same = False
    if not same and legacy.exists() and legacy.is_dir():
        for child in legacy.iterdir():
            if not child.is_dir() or child.name == ".app":
                continue
            destination = target_workspace / child.name
            if destination.exists():
                continue
            try:
                shutil.copytree(child, destination)
            except OSError:
                # Persistence must remain usable even if an old release folder
                # cannot be read. The user can still choose/copy data manually.
                continue
    try:
        marker.write_text("adopted\n", encoding="utf-8")
    except OSError:
        pass


def workspace_root() -> Path:
    """Compatibility name for the persistent per-site container.

    Existing application code still calls this a workspace. Its physical
    location is now under Project Data rather than under the release folder.
    """
    root = project_data_root() / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    _adopt_legacy_release_workspace(root)
    return root


def is_inside_workspace(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(workspace_root().resolve())
        return True
    except ValueError:
        return False


def bundled_standard_reference_path() -> Path:
    """Immutable STANDARD workbook shipped with the application release."""
    return resource_root() / "templates" / "IOA STANDARD.xlsx"


def standard_reference_root() -> Path:
    """Writable application-wide STANDARD reference area."""
    root = user_data_root() / "reference"
    root.mkdir(parents=True, exist_ok=True)
    return root


def standard_reference_library_dir() -> Path:
    """Directory containing user-uploaded STANDARD workbook versions."""
    root = standard_reference_root() / "standards"
    root.mkdir(parents=True, exist_ok=True)
    return root


def standard_override_path() -> Path:
    """Legacy single user STANDARD path retained for upgrade compatibility."""
    return standard_reference_root() / "IOA STANDARD.xlsx"


def standard_reference_metadata_path() -> Path:
    return standard_reference_root() / "standard_reference.json"


def _standard_reference_selection() -> dict:
    path = standard_reference_metadata_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def standard_reference_path() -> Path:
    """Return the explicitly selected STANDARD workbook used by review/export.

    Selection is deterministic and never follows "latest file" heuristics:
      1. explicit user-library selection recorded in metadata;
      2. explicit built-in selection;
      3. legacy v0.8.x single override (upgrade compatibility);
      4. bundled release reference.
    """
    meta = _standard_reference_selection()
    active = meta.get("active") if isinstance(meta.get("active"), dict) else {}
    kind = str(active.get("kind") or "").strip().casefold()
    filename = Path(str(active.get("filename") or "")).name
    if kind == "user" and filename:
        candidate = standard_reference_library_dir() / filename
        if candidate.exists():
            return candidate
    if kind == "legacy":
        legacy = standard_override_path()
        if legacy.exists():
            return legacy
    if kind == "built-in":
        return bundled_standard_reference_path()

    legacy = standard_override_path()
    if legacy.exists():
        return legacy
    return bundled_standard_reference_path()


def standard_reference_origin() -> str:
    path = standard_reference_path()
    try:
        if path.resolve() == bundled_standard_reference_path().resolve():
            return "Built-in"
    except OSError:
        pass
    try:
        path.resolve().relative_to(standard_reference_library_dir().resolve())
        return "User Library"
    except (OSError, ValueError):
        pass
    if path == standard_override_path():
        return "Legacy User Override"
    return "User Library"
