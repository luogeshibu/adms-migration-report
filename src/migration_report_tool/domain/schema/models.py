"""Canonical source-schema contracts used by every tabular input.

External CSV/XLSX headers are never consumed directly by business logic.  Each
source is resolved to a stable canonical model first.  This prevents a renamed
site column from silently turning into a blank value and then being interpreted
as a successful consistency check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class MappingKind(str, Enum):
    EXACT = "Exact"
    ALIAS = "Built-in Alias"
    OVERRIDE = "Site Override"
    BLANK = "Blank · no source"
    MISSING = "Missing"
    AMBIGUOUS = "Ambiguous"


class SchemaLevel(str, Enum):
    READY = "READY"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    aliases: tuple[str, ...]
    required: bool = False
    warn_if_missing: bool = True
    description: str = ""

    @property
    def preferred_header(self) -> str:
        return self.aliases[0] if self.aliases else self.label


@dataclass(frozen=True)
class SourceSchema:
    source_type: str
    label: str
    fields: tuple[FieldSpec, ...]
    sheet_name: str | None = None
    header_scan_rows: int = 1

    def field(self, key: str) -> FieldSpec:
        for item in self.fields:
            if item.key == key:
                return item
        raise KeyError(key)


@dataclass(frozen=True)
class FieldMapping:
    canonical_key: str
    canonical_label: str
    actual_column: str | None
    required: bool
    kind: MappingKind
    candidates: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class SchemaValidationResult:
    schema: SourceSchema
    headers: tuple[str, ...]
    mappings: tuple[FieldMapping, ...]
    ignored_columns: tuple[str, ...] = ()

    @property
    def errors(self) -> tuple[FieldMapping, ...]:
        return tuple(m for m in self.mappings if m.kind in {MappingKind.AMBIGUOUS} or (m.required and m.kind == MappingKind.MISSING))

    @property
    def warnings(self) -> tuple[FieldMapping, ...]:
        return tuple(
            m for m in self.mappings
            if (
                (
                    m.kind == MappingKind.BLANK
                    and self.schema.field(m.canonical_key).warn_if_missing
                )
                or (
                    not m.required
                    and m.kind == MappingKind.MISSING
                    and self.schema.field(m.canonical_key).warn_if_missing
                )
            )
        )

    @property
    def level(self) -> SchemaLevel:
        if self.errors:
            return SchemaLevel.ERROR
        if self.warnings:
            return SchemaLevel.WARNING
        return SchemaLevel.READY

    @property
    def mapping_by_key(self) -> dict[str, FieldMapping]:
        return {m.canonical_key: m for m in self.mappings}

    def mapped_column(self, canonical_key: str) -> str | None:
        mapping = self.mapping_by_key.get(canonical_key)
        return mapping.actual_column if mapping else None

    def error_message(self, file_name: str = "source file") -> str:
        if not self.errors:
            return ""
        lines = [f"{self.schema.label} schema validation failed: {file_name}", ""]
        for mapping in self.errors:
            spec = self.schema.field(mapping.canonical_key)
            lines.append(f"Field: {spec.label} ({'required' if spec.required else 'optional'})")
            if mapping.kind == MappingKind.AMBIGUOUS:
                lines.append("Problem: multiple configured columns matched: " + ", ".join(mapping.candidates))
                lines.append("Select the correct column in Source Mapping before continuing.")
            else:
                lines.append("Problem: no matching column was found.")
                lines.append("Expected column names: " + ", ".join(spec.aliases))
            lines.append("")
        lines.append("Detected columns: " + (", ".join(self.headers) if self.headers else "<none>"))
        return "\n".join(lines)


class SchemaValidationError(ValueError):
    def __init__(self, result: SchemaValidationResult, file_name: str = "source file"):
        self.result = result
        self.file_name = file_name
        super().__init__(result.error_message(file_name))
