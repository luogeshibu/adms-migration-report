"""Source adapters isolate review engines from files and future databases."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

from ...domain.schema import SchemaValidationError
from ..parsers import read_mapped_rows
from ...storage import ProjectStore


class SourceAdapter(ABC):
    @abstractmethod
    def load_rows(self, source_type: str) -> list[dict]:
        raise NotImplementedError

    def zenon_xml_path(self) -> Path | None:
        return None


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
        mapped = read_mapped_rows(source_type, path, overrides, strict=True)
        return list(mapped.rows)

    def zenon_xml_path(self) -> Path | None:
        return self.store.source_path("zenon_xml")


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
