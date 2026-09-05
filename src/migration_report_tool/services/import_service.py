"""Source import/synchronization service with schema validation."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..infrastructure.parsers import read_mapped_rows, validate_source_file
from ..storage import ProjectStore


@dataclass(frozen=True)
class ImportResult:
    source_type: str
    original_path: Path
    stored_path: Path
    row_count: int
    mapping_required: bool = False
    mapping_message: str = ""
    detected_headers: tuple[str, ...] = ()


def import_source(
    store: ProjectStore, source_type: str, selected: Path, *, allow_unresolved_mapping: bool = False
) -> ImportResult:
    """Archive and register one source file, with optional remap-first staging.

    Normal imports remain strict.  Interactive Source File replacement may pass
    ``allow_unresolved_mapping=True`` so a file whose physical headers changed
    can still become the active/staged source and be opened in Map Fields.  In
    that mode required schema mismatches are *not* interpreted as bad data: the
    source is copied safely, dependent Analysis is held at the previous result,
    and the reviewer must explicitly remap the required App Columns before the
    new source is used for validation.
    """
    selected = Path(selected)
    if not selected.exists():
        raise FileNotFoundError(str(selected))

    overrides = store.source_column_overrides(source_type)
    suffix = selected.suffix.lower()
    validation = None
    mapping_required = False
    mapping_message = ""
    detected_headers: tuple[str, ...] = ()
    sheet_name = store.source_sheet_name(source_type) if suffix in {".xlsx", ".xlsm"} and hasattr(store, "source_sheet_name") else ""
    if suffix in {".csv", ".xlsx", ".xlsm"}:
        validation = validate_source_file(source_type, selected, overrides, sheet_name=sheet_name or None)
        if validation is not None:
            detected_headers = tuple(validation.headers or ())
        if validation is not None and validation.errors:
            if not allow_unresolved_mapping:
                from ..domain.schema import SchemaValidationError
                raise SchemaValidationError(validation, selected.name)
            mapping_required = True
            mapping_message = validation.error_message(selected.name)

    # Even when mapping is unresolved, keep a safe workspace snapshot of the
    # explicitly selected physical file. This is what Map Fields must inspect;
    # the previous comparison result is left untouched until a valid mapping is
    # saved and the source is reloaded successfully.
    stored = store.set_source(source_type, selected)
    count = 0
    if suffix in {".csv", ".xlsx", ".xlsm"} and not mapping_required:
        count = len(read_mapped_rows(source_type, stored, overrides, strict=True, sheet_name=sheet_name or None).rows)
    store.db.execute(
        "INSERT INTO imports(source_type,original_name,stored_path,imported_at,row_count) VALUES(?,?,?,?,?)",
        (source_type, selected.name, str(stored), datetime.now().isoformat(timespec="seconds"), count),
    )
    store.db.commit()
    return ImportResult(
        source_type, selected, stored, count,
        mapping_required=mapping_required,
        mapping_message=mapping_message,
        detected_headers=detected_headers,
    )
