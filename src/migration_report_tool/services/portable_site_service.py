"""Unified site storage and one-time migration support."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import shutil
import sqlite3

from ..parsers import clean
from .configurable_comparison_service import (
    CONFIG_KEY,
    get_config,
    get_signal_source_assignments,
    resolve_signal_source_assignment,
    source_path as configurable_source_path,
)

PORTABLE_SITE_MARKER = "PORTABLE_SITE.json"
SUPPORTED_SOURCE_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}
_IGNORED_SOURCE_DIRS = {".git", "__pycache__", "archive", "backup", "backups", "generated", "reports", "snapshots"}


def migrate_legacy_project_data(legacy_folder: Path | str, site_folder: Path | str) -> bool:
    """Adopt an existing per-site database into the site folder once.

    New versions keep ``project.db`` beside the source workbooks.  When an
    older installation already has a database under Project Data, copy it
    into the site directory before opening the new ProjectStore.  The legacy
    files are intentionally left untouched so this operation is recoverable.
    """
    legacy = Path(legacy_folder).resolve()
    site = Path(site_folder).resolve()
    source_db = legacy / "project.db"
    target_db = site / "project.db"
    if target_db.exists() or not source_db.is_file():
        return False
    site.mkdir(parents=True, exist_ok=True)
    try:
        # A SQLite backup includes committed WAL content and is safer than
        # copying only project.db while an older build still has sidecars.
        source = sqlite3.connect(str(source_db), timeout=15.0)
        target = sqlite3.connect(str(target_db), timeout=15.0)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
    except Exception:
        # Keep a simple-file fallback for old/partially-created databases.
        if target_db.exists():
            target_db.unlink()
        shutil.copy2(source_db, target_db)
    legacy_json = legacy / "project.json"
    target_json = site / "project.json"
    if legacy_json.is_file() and not target_json.exists():
        shutil.copy2(legacy_json, target_json)
    return True


def is_portable_site_folder(path: Path | str) -> bool:
    root = Path(path)
    return (root / PORTABLE_SITE_MARKER).is_file() and (root / "project.db").is_file()


def is_unified_site_folder(path: Path | str) -> bool:
    """Return whether a site keeps its Project Data beside its source files.

    The marker identifies packages created by the one-time migration action.
    A database plus at least one tabular file also identifies a normal site
    created directly in the new unified layout, so future sites do not need a
    second migration step.  A legacy workspace containing only ``project.db``
    is deliberately not classified as unified.
    """
    root = Path(path)
    if not (root / "project.db").is_file():
        return False
    if (root / PORTABLE_SITE_MARKER).is_file():
        return True
    # A legacy project workspace may already contain internal
    # ``source_files`` snapshots. Those alone must not make it look unified.
    return bool(_candidate_source_files(root, include_source_files=False))


def _candidate_source_files(root: Path, *, include_source_files: bool = True) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
                continue
            relative_parts = path.relative_to(root).parts[:-1]
            ignored = set(_IGNORED_SOURCE_DIRS)
            if not include_source_files:
                ignored.add("source_files")
            if any(part.startswith(".") or part.casefold() in ignored for part in relative_parts):
                continue
            result.append(path)
        except (OSError, ValueError):
            continue
    return sorted(result, key=lambda item: str(item).casefold())


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left).casefold() == str(right).casefold()


def _copy_into_package(source: Path, package: Path, used_names: dict[str, Path]) -> Path:
    """Copy one source into a package subdirectory without overwriting another source."""
    source = Path(source).resolve()
    package.mkdir(parents=True, exist_ok=True)
    name = source.name
    stem = source.stem
    suffix = source.suffix.lower()
    counter = 1
    while True:
        target = package / name
        previous = used_names.get(name.casefold())
        if previous is None and not target.exists():
            break
        if previous is not None and _same_path(previous, source):
            return target
        counter += 1
        name = f"{stem}__{counter}{suffix}"
    shutil.copy2(source, target)
    used_names[name.casefold()] = source
    return target


def repair_unified_site_paths(store, site_path: Path | str | None = None) -> int:
    """Repair source links in an existing unified site without touching review data.

    Early versions of the one-time migration action could copy the workbooks
    successfully but leave an old absolute source path in ``project.json``.
    When a unified site is opened, resolve matching filenames from the site
    folder and persist only the source-link repair.  The SQLite project data is
    never rewritten by this repair.
    """
    package = Path(site_path or store.folder).resolve()
    if not is_unified_site_folder(package):
        return 0
    local_files = _candidate_source_files(package)
    by_name: dict[str, list[Path]] = {}
    for path in local_files:
        by_name.setdefault(path.name.casefold(), []).append(path)

    changed = 0

    def local_match(raw_path: object) -> Path | None:
        text = str(raw_path or "").strip()
        if not text:
            return None
        candidate = Path(text)
        if candidate.is_absolute():
            name = candidate.name
        else:
            name = candidate.name
        matches = by_name.get(name.casefold(), [])
        return matches[0] if len(matches) == 1 else None

    config = get_config(store, bootstrap=False)
    for source in config.get("sources", []):
        current = configurable_source_path(store, source)
        target = local_match(source.get("path"))
        if target is None and current is not None:
            target = local_match(current)
        if target is None:
            continue
        relative = target.relative_to(package).as_posix()
        if source.get("path") != relative or source.get("path_mode") != "project_relative":
            source["path"] = relative
            source["path_mode"] = "project_relative"
            source["family_key"] = source.get("family_key") or target.stem.casefold()
            source["family_suffix"] = target.suffix.lower()
            changed += 1
    if config.get("sources"):
        store.config[CONFIG_KEY] = config

    signal_root = dict((store.config or {}).get("signal_mapping_source_assignments_v1") or {})
    for role, assignment in signal_root.items():
        assignment = dict(assignment or {})
        current = resolve_signal_source_assignment(store, role)
        target = local_match(assignment.get("path"))
        if target is None and current is not None:
            target = local_match(current)
        if target is None:
            continue
        relative = target.relative_to(package).as_posix()
        if assignment.get("path") != relative or assignment.get("path_mode") != "project_relative":
            assignment["path"] = relative
            assignment["path_mode"] = "project_relative"
            signal_root[role] = assignment
            changed += 1
    if signal_root:
        store.config["signal_mapping_source_assignments_v1"] = signal_root

    if changed:
        store.save_config()
    return changed


def ensure_unified_site_marker(folder: Path | str, *, site_name: str = "") -> Path:
    """Create the stable marker used by future in-place sites."""
    root = Path(folder).resolve()
    root.mkdir(parents=True, exist_ok=True)
    marker = root / PORTABLE_SITE_MARKER
    if not marker.exists():
        marker.write_text(
            json.dumps(
                {
                    "format": 1,
                    "layout": "unified-site",
                    "site_name": clean(site_name) or root.name,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return marker


def organize_unified_site(store, site_path: Path | str | None = None) -> int:
    """Move root-level source tables into ``source_files`` and repair links.

    Database, comments, audit history and generated folders are never moved.
    Existing root-level packages remain readable while the application adopts
    the organized layout; future imports already use ``source_files``.
    """
    package = Path(site_path or store.folder).resolve()
    if not is_unified_site_folder(package):
        return 0
    source_dir = package / "source_files"
    reports_dir = package / "reports"
    source_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    used_names = {item.name.casefold() for item in source_dir.iterdir() if item.is_file()}
    report_names = {item.name.casefold() for item in reports_dir.iterdir() if item.is_file()}

    config = get_config(store, bootstrap=False)
    configured_names: set[str] = set()
    for source in config.get("sources", []):
        path = configurable_source_path(store, source)
        if path is not None:
            configured_names.add(path.name.casefold())
    for role in get_signal_source_assignments(store):
        path = resolve_signal_source_assignment(store, role)
        if path is not None:
            configured_names.add(path.name.casefold())

    def move_unique(source: Path, destination: Path, names: set[str]) -> None:
        stem = source.stem
        suffix = source.suffix
        name = source.name
        counter = 1
        while name.casefold() in names:
            counter += 1
            name = f"{stem}__{counter}{suffix}"
        shutil.move(str(source), str(destination / name))
        names.add(name.casefold())

    moved = 0
    for source in sorted(package.iterdir(), key=lambda item: item.name.casefold()):
        if not source.is_file() or source.suffix.lower() not in SUPPORTED_SOURCE_EXTENSIONS:
            continue
        # Files already bound to a configured source role are source inputs.
        # Other obvious report workbooks belong with generated deliverables;
        # unknown tables remain portable inputs by default.
        if source.name.casefold() in configured_names or "report" not in source.stem.casefold():
            move_unique(source, source_dir, used_names)
        else:
            move_unique(source, reports_dir, report_names)
        moved += 1
    ensure_unified_site_marker(package, site_name=package.name)
    repair_unified_site_paths(store, package)
    return moved


def prepare_portable_site(store, repository_site_path: Path | str) -> dict:
    """Merge live source workbooks into the current Project Data site.

    This operation is intentionally explicit and one-time, but it is valid at
    any review status. It never removes or modifies the original repository
    files. The existing project database remains the authority for comments,
    Checked state, Review status, Resolution decisions and audit history.
    """
    package = Path(store.folder).resolve()
    repository = Path(repository_site_path).resolve()
    if not repository.is_dir():
        raise ValueError(f"Source site folder is unavailable: {repository}")
    if is_unified_site_folder(package):
        raise ValueError("This site already uses the unified site data layout.")

    package.mkdir(parents=True, exist_ok=True)
    source_paths: list[Path] = _candidate_source_files(repository)

    # Include configured files that were manually selected outside the normal
    # repository tree.  This keeps arbitrary customer-provided tables portable
    # as well as the standard source files.
    config = get_config(store, bootstrap=False)
    for source in config.get("sources", []):
        path = configurable_source_path(store, source)
        if path and path.exists() and path.is_file():
            source_paths.append(Path(path))
    for role in get_signal_source_assignments(store):
        path = resolve_signal_source_assignment(store, role)
        if path and path.exists() and path.is_file():
            source_paths.append(Path(path))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in source_paths:
        try:
            resolved = Path(path).resolve()
        except OSError:
            resolved = Path(path)
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(resolved)

    source_dir = package / "source_files"
    source_dir.mkdir(parents=True, exist_ok=True)
    used_names: dict[str, Path] = {
        item.name.casefold(): item
        for item in source_dir.iterdir()
        if item.is_file()
    }
    copied: dict[str, Path] = {}
    for source in unique:
        if not source.exists() or not source.is_file():
            continue
        target = _copy_into_package(source, source_dir, used_names) if not _same_path(source, source_dir / source.name) else source
        copied[str(source).casefold()] = target

    def packaged_path(path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            resolved = Path(path).resolve()
        except OSError:
            resolved = Path(path)
        target = copied.get(str(resolved).casefold())
        if target is not None:
            return target
        try:
            resolved.relative_to(package)
            return resolved
        except ValueError:
            return None

    # Rebind configurable Equipment and Signal sources to the package itself.
    # ``project_relative`` is resolved against ProjectStore.folder and survives
    # drive-letter and machine changes.
    for source in config.get("sources", []):
        active = configurable_source_path(store, source)
        target = packaged_path(active)
        if target is None:
            continue
        source["path"] = target.relative_to(package).as_posix()
        source["path_mode"] = "project_relative"
        source["family_key"] = source.get("family_key") or target.stem.casefold()
        source["family_suffix"] = target.suffix.lower()
    # get_config() returns a normalized copy. Put the updated equipment source
    # links back into the persistent project configuration before saving; this
    # is what makes the copied files usable after the original drive/path is
    # unavailable on the destination machine.
    store.config[CONFIG_KEY] = config

    signal_root = dict((store.config or {}).get("signal_mapping_source_assignments_v1") or {})
    for role, assignment in signal_root.items():
        active = resolve_signal_source_assignment(store, role)
        target = packaged_path(active)
        if target is None:
            continue
        assignment = dict(assignment or {})
        assignment["path"] = target.relative_to(package).as_posix()
        assignment["path_mode"] = "project_relative"
        signal_root[role] = assignment
    if signal_root:
        store.config["signal_mapping_source_assignments_v1"] = signal_root

    # Manual legacy imports keep their role and history, but their live/original
    # pointer must also become local when the file was packaged.
    manual = dict((store.config or {}).get("manual_source_overrides") or {})
    for role, record in manual.items():
        original = Path(str((record or {}).get("original_path") or ""))
        target = packaged_path(original) if str(original) else None
        if target is not None:
            updated = dict(record or {})
            updated["original_path"] = str(target)
            updated["original_name"] = target.name
            manual[role] = updated
    if manual:
        store.config["manual_source_overrides"] = manual

    prepared_at = datetime.now().isoformat(timespec="seconds")
    store.config["portable_site_package"] = {
        "marker": PORTABLE_SITE_MARKER,
        "prepared_at": prepared_at,
        "source_site": str(repository),
        "source_count": len(copied),
    }
    store.save_config()
    marker = {
        "format": 1,
        "site_name": clean(store.config.get("site_name") or package.name),
        "prepared_at": prepared_at,
        "source_count": len(copied),
        "instructions": "Copy this entire folder to another machine and select this folder as Source Workspace.",
    }
    (package / PORTABLE_SITE_MARKER).write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"package": package, "source_count": len(copied), "marker": package / PORTABLE_SITE_MARKER}
