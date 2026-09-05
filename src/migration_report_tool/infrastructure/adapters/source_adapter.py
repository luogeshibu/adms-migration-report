"""Source adapters isolate review engines from files and future databases."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

from ...domain.schema import SchemaValidationError
from ..parsers import read_mapped_rows, read_csv_raw, read_excel_raw
from ...storage import ProjectStore


class SourceAdapter(ABC):
    @abstractmethod
    def load_rows(self, source_type: str) -> list[dict]:
        raise NotImplementedError


class WorkspaceFileAdapter(SourceAdapter):
    """Read archived workspace sources through canonical schema mapping."""
    def __init__(self, store: ProjectStore):
        self.store = store

    def load_rows(self, source_type: str) -> list[dict]:
        path = self.store.source_path(source_type)
        if not path:
            return []
        if path.suffix.lower() not in {".csv", ".xlsx", ".xlsm"}:
            return []
        overrides = self.store.source_column_overrides(source_type)
        sheet_name = self.store.source_sheet_name(source_type) if path.suffix.lower() in {".xlsx", ".xlsm"} and hasattr(self.store, "source_sheet_name") else ""
        mapped = read_mapped_rows(source_type, path, overrides, strict=True, sheet_name=sheet_name or None)
        rows = [dict(row) for row in mapped.rows]

        # USER App columns use application-global Source Field selections and
        # travel with the canonical row. This lets RMU Data Review expose a
        # newly added field immediately after Validation without changing the
        # fixed automatic Analysis schema.
        custom_fields = list(self.store.custom_source_fields(source_type) or [])
        if custom_fields:
            if path.suffix.lower() == ".csv":
                _headers, raw_rows = read_csv_raw(path)
            else:
                _headers, raw_rows = read_excel_raw(path, sheet_name=sheet_name or None)
            for index, row in enumerate(rows):
                raw = raw_rows[index] if index < len(raw_rows) else {}
                for item in custom_fields:
                    key = str((item or {}).get("field_key") or "").strip()
                    actual = str((item or {}).get("actual_column") or "").strip()
                    if key:
                        row[key] = raw.get(actual) if actual else None
        return rows

class DBAPIQueryAdapter(SourceAdapter):
    """Database-ready adapter.

    SQL queries should alias result columns to the canonical field names defined
    by SourceSchema. This makes database and file inputs interchangeable.
    """
    def __init__(self, connection_factory, queries: dict[str, str]):
        self.connection_factory = connection_factory
        self.queries = dict(queries)

    def load_rows(self, source_type: str) -> list[dict]:
        query = self.queries.get(source_type)
        if not query:
            return []
        conn = self.connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            names = [str(col[0]) for col in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]
        finally:
            try:
                conn.close()
            except Exception:
                pass
