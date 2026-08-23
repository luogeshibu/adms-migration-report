"""Manage the application-wide IOA STANDARD reference workbook."""
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
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def current_standard_reference_info() -> StandardReferenceInfo:
    path = standard_reference_path()
    _validation, mapped = validate_standard_reference(path)
    metadata = _read_metadata() if standard_reference_origin() == "User Override" else {}
    updated_at = str(metadata.get("updated_at") or datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"))
    original_name = str(metadata.get("original_name") or path.name)
    return StandardReferenceInfo(
        path=path,
        origin=standard_reference_origin(),
        row_count=len(mapped.rows),
        sha256=_sha256(path),
        updated_at=updated_at,
        original_name=original_name,
    )


def install_standard_reference(source: Path, modified_by: str = "") -> StandardReferenceInfo:
    """Validate then install a user STANDARD override atomically enough for UI use."""
    source = Path(source).resolve()
    _validation, mapped = validate_standard_reference(source)
    target = standard_override_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        backup_dir = target.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(target, backup_dir / f"IOA STANDARD-{stamp}.xlsx")

    tmp = target.with_suffix(".tmp.xlsx")
    shutil.copy2(source, tmp)
    tmp.replace(target)
    now = datetime.now().isoformat(timespec="seconds")
    metadata = {
        "original_name": source.name,
        "installed_path": str(target),
        "updated_at": now,
        "modified_by": modified_by or "system",
        "row_count": len(mapped.rows),
        "sha256": _sha256(target),
    }
    standard_reference_metadata_path().write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return current_standard_reference_info()


def restore_bundled_standard_reference() -> StandardReferenceInfo:
    """Remove the user override and immediately fall back to the bundled table."""
    override = standard_override_path()
    if override.exists():
        override.unlink()
    metadata = standard_reference_metadata_path()
    if metadata.exists():
        metadata.unlink()
    bundled = bundled_standard_reference_path()
    if not bundled.exists():
        raise FileNotFoundError(f"Bundled IOA STANDARD reference not found: {bundled}")
    return current_standard_reference_info()
