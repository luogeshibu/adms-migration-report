"""Manage the application-wide STANDARD workbook library and active selection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil

from ..infrastructure.parsers import read_mapped_rows, validate_source_file
from ..utils.paths import (
    bundled_standard_reference_path,
    standard_override_path,
    standard_reference_library_dir,
    standard_reference_metadata_path,
    standard_reference_origin,
    standard_reference_path,
)


@dataclass(frozen=True)
class StandardReferenceInfo:
    path: Path
    origin: str
    row_count: int
    sha256: str
    updated_at: str
    original_name: str
    key: str = ""
    active: bool = False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_standard_reference(path: Path):
    """Validate STANDARD sheet and required Type/IOA/name columns."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("STANDARD reference must be an Excel workbook (.xlsx or .xlsm).")
    validation = validate_source_file("standard_reference", path, {})
    if validation is None:
        raise ValueError("IOA STANDARD schema is not configured.")
    if validation.errors:
        raise ValueError(validation.error_message(path.name))
    mapped = read_mapped_rows("standard_reference", path, {}, strict=True)
    if not mapped.rows:
        raise ValueError("STANDARD sheet contains no data rows.")
    return validation, mapped


def _read_metadata() -> dict:
    path = standard_reference_metadata_path()
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_metadata(payload: dict) -> None:
    path = standard_reference_metadata_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _active_descriptor() -> dict:
    meta = _read_metadata()
    active = meta.get("active")
    if isinstance(active, dict):
        return dict(active)
    # v0.8.135 and older metadata represented one installed override. Preserve it
    # without deleting or rewriting the old workbook.
    legacy = standard_override_path()
    if legacy.exists():
        return {"kind": "legacy", "filename": legacy.name}
    return {"kind": "built-in", "filename": bundled_standard_reference_path().name}


def _key_for(kind: str, path: Path) -> str:
    if kind == "built-in":
        return "builtin"
    if kind == "legacy":
        return "legacy"
    return f"user:{Path(path).name.casefold()}"


def _info_for(path: Path, origin: str, *, key: str, active: bool) -> StandardReferenceInfo:
    _validation, mapped = validate_standard_reference(path)
    meta = _read_metadata()
    per_file = (meta.get("files") or {}).get(path.name, {}) if origin == "User Library" else {}
    legacy_meta = meta if origin == "Legacy User Override" and not meta.get("active") else {}
    updated_at = str(
        per_file.get("updated_at")
        or legacy_meta.get("updated_at")
        or datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    )
    original_name = str(per_file.get("original_name") or legacy_meta.get("original_name") or path.name)
    return StandardReferenceInfo(
        path=path,
        origin=origin,
        row_count=len(mapped.rows),
        sha256=_sha256(path),
        updated_at=updated_at,
        original_name=original_name,
        key=key,
        active=active,
    )


def list_standard_references(*, validate: bool = True) -> list[StandardReferenceInfo]:
    """Return every available STANDARD workbook; active selection is explicit."""
    active_path = standard_reference_path()
    result: list[StandardReferenceInfo] = []

    def append(path: Path, origin: str, key: str) -> None:
        if not path.exists():
            return
        active = False
        try:
            active = path.resolve() == active_path.resolve()
        except OSError:
            active = path == active_path
        if validate:
            try:
                result.append(_info_for(path, origin, key=key, active=active))
            except Exception:
                # Invalid library files should not become active candidates in UI.
                return
        else:
            result.append(StandardReferenceInfo(
                path=path, origin=origin, row_count=0, sha256="",
                updated_at=datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                original_name=path.name, key=key, active=active,
            ))

    append(bundled_standard_reference_path(), "Built-in", "builtin")

    library = standard_reference_library_dir()
    for path in sorted(
        [p for p in library.iterdir() if p.is_file() and p.suffix.lower() in {".xlsx", ".xlsm"}],
        key=lambda p: (p.name.casefold(), p.name),
    ):
        append(path, "User Library", _key_for("user", path))

    legacy = standard_override_path()
    if legacy.exists():
        # Avoid a duplicate visual entry only when it is physically the active
        # user-library file (normally they are different paths).
        append(legacy, "Legacy User Override", "legacy")
    return result


def current_standard_reference_info() -> StandardReferenceInfo:
    path = standard_reference_path()
    origin = standard_reference_origin()
    key = "builtin" if origin == "Built-in" else ("legacy" if origin == "Legacy User Override" else _key_for("user", path))
    return _info_for(path, origin, key=key, active=True)


def add_standard_reference(source: Path, modified_by: str = "", *, overwrite: bool = False) -> StandardReferenceInfo:
    """Validate and add one workbook to the persistent STANDARD library.

    File name is the version identity shown to users. A same-name upload never
    overwrites silently; callers must pass ``overwrite=True`` after user consent.
    Uploading does not change the active STANDARD selection.
    """
    source = Path(source).resolve()
    _validation, mapped = validate_standard_reference(source)
    library = standard_reference_library_dir()
    library.mkdir(parents=True, exist_ok=True)
    target = library / source.name

    same_physical = False
    try:
        same_physical = source.resolve() == target.resolve()
    except OSError:
        pass
    if target.exists() and not same_physical and not overwrite:
        raise FileExistsError(target)

    if target.exists() and not same_physical and overwrite:
        backup_dir = library / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{target.stem}-{stamp}{target.suffix}"
        shutil.copy2(target, backup)

    if not same_physical:
        tmp = target.with_name(target.name + ".tmp")
        shutil.copy2(source, tmp)
        tmp.replace(target)

    meta = _read_metadata()
    files = dict(meta.get("files") or {})
    now = datetime.now().isoformat(timespec="seconds")
    files[target.name] = {
        "original_name": source.name,
        "installed_path": str(target),
        "updated_at": now,
        "modified_by": modified_by or "system",
        "row_count": len(mapped.rows),
        "sha256": _sha256(target),
    }
    meta["files"] = files
    # Never silently change the active reference when merely uploading.
    if not isinstance(meta.get("active"), dict):
        active = _active_descriptor()
        meta["active"] = active
    _write_metadata(meta)
    return _info_for(target, "User Library", key=_key_for("user", target), active=False)


def activate_standard_reference(key: str, modified_by: str = "") -> StandardReferenceInfo:
    """Explicitly select one STANDARD workbook for all sites and exports."""
    key = str(key or "").strip()
    if key == "builtin":
        path = bundled_standard_reference_path()
        kind = "built-in"
        filename = path.name
    elif key == "legacy":
        path = standard_override_path()
        kind = "legacy"
        filename = path.name
    elif key.startswith("user:"):
        wanted = key.split(":", 1)[1].casefold()
        candidates = [p for p in standard_reference_library_dir().iterdir() if p.is_file() and p.name.casefold() == wanted]
        if not candidates:
            raise FileNotFoundError(f"STANDARD library entry not found: {key}")
        path = candidates[0]
        kind = "user"
        filename = path.name
    else:
        raise ValueError(f"Unknown STANDARD reference selection: {key}")

    validate_standard_reference(path)
    meta = _read_metadata()
    meta["active"] = {
        "kind": kind,
        "filename": filename,
        "selected_at": datetime.now().isoformat(timespec="seconds"),
        "selected_by": modified_by or "system",
    }
    _write_metadata(meta)
    return current_standard_reference_info()


def install_standard_reference(source: Path, modified_by: str = "") -> StandardReferenceInfo:
    """Backward-compatible one-step API: add and explicitly activate a workbook."""
    info = add_standard_reference(source, modified_by, overwrite=True)
    return activate_standard_reference(info.key, modified_by)


def restore_bundled_standard_reference() -> StandardReferenceInfo:
    """Select bundled STANDARD without deleting any uploaded reference/version."""
    return activate_standard_reference("builtin", "system")
