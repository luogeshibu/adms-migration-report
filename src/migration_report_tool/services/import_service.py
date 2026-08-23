"""Source import/synchronization service with schema validation."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..comparison import write_zenon_sld_csv
from ..infrastructure.parsers import read_mapped_rows, validate_source_file
from ..parsers import parse_zenon_xml
from ..storage import ProjectStore


@dataclass(frozen=True)
class ImportResult:
    source_type: str
    original_path: Path
    stored_path: Path
    row_count: int


def import_source(store: ProjectStore, source_type: str, selected: Path) -> ImportResult:
    """Validate, archive and register one source file.

    Tabular inputs are validated *before* they enter the workspace. Required
    columns missing from a source therefore fail loudly instead of becoming
    blank canonical values later in Analysis.
    """
    selected = Path(selected)
    if not selected.exists():
        raise FileNotFoundError(str(selected))

    overrides = store.source_column_overrides(source_type)
    suffix = selected.suffix.lower()
    if suffix in {".csv", ".xlsx", ".xlsm"}:
        validation = validate_source_file(source_type, selected, overrides)
        if validation is not None and validation.errors:
            from ..domain.schema import SchemaValidationError
            raise SchemaValidationError(validation, selected.name)

    stored = store.set_source(source_type, selected)
    count = 0
    if source_type == "zenon_xml":
        site_name = str(store.config.get("repository_site") or store.config.get("site_name") or "").strip()
        se_feeders = []
        se_path = store.source_path("se_list")
        if se_path and se_path.suffix.lower() in {".xlsx", ".xlsm"}:
            try:
                se_rows = read_mapped_rows("se_list", se_path, store.source_column_overrides("se_list"), strict=True).rows
                se_feeders = [str(row.get("feeder") or "").strip() for row in se_rows]
                se_feeders = [value for value in se_feeders if value]
            except Exception:
                se_feeders = []
        parsed = parse_zenon_xml(stored, site_name=site_name or None, allowed_feeders=se_feeders)
        write_zenon_sld_csv(store, stored, parsed)
        count = len(parsed)
    elif suffix in {".csv", ".xlsx", ".xlsm"}:
        count = len(read_mapped_rows(source_type, stored, overrides, strict=True).rows)

    store.db.execute(
        "INSERT INTO imports(source_type,original_name,stored_path,imported_at,row_count) VALUES(?,?,?,?,?)",
        (source_type, selected.name, str(stored), datetime.now().isoformat(timespec="seconds"), count),
    )
    store.db.commit()
    return ImportResult(source_type, selected, stored, count)
