"""Deterministic header matching with no semantic guessing."""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from .models import (
    FieldMapping,
    MappingKind,
    SchemaValidationResult,
    SourceSchema,
)


def normalize_header(value: object) -> str:
    """Normalize only syntactic header differences, never business meaning.

    BOM, surrounding whitespace, case, spaces, underscores and punctuation are
    ignored.  Semantic alternatives such as DEVICE -> RMU Type are allowed only
    when explicitly declared as aliases in the SourceSchema.
    """
    text = "" if value is None else str(value)
    text = text.replace("\ufeff", "").strip().casefold()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def _unique_headers(headers: Sequence[object]) -> tuple[str, ...]:
    result: list[str] = []
    for header in headers:
        text = "" if header is None else str(header).replace("\ufeff", "").strip()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def resolve_schema(
    schema: SourceSchema,
    headers: Sequence[object],
    overrides: Mapping[str, str] | None = None,
) -> SchemaValidationResult:
    overrides = {str(k): str(v) for k, v in (overrides or {}).items() if str(v).strip()}
    actual_headers = _unique_headers(headers)
    normalized_actual: dict[str, list[str]] = {}
    for header in actual_headers:
        normalized_actual.setdefault(normalize_header(header), []).append(header)

    mappings: list[FieldMapping] = []
    used: set[str] = set()
    for spec in schema.fields:
        override = overrides.get(spec.key, "").strip()
        if override:
            candidates = normalized_actual.get(normalize_header(override), [])
            if len(candidates) == 1:
                actual = candidates[0]
                used.add(actual)
                mappings.append(FieldMapping(spec.key, spec.label, actual, spec.required, MappingKind.OVERRIDE))
                continue
            if len(candidates) > 1:
                mappings.append(FieldMapping(
                    spec.key, spec.label, None, spec.required, MappingKind.AMBIGUOUS,
                    tuple(candidates), f"Site override '{override}' matches more than one column.",
                ))
                continue
            mappings.append(FieldMapping(
                spec.key, spec.label, None, spec.required, MappingKind.MISSING,
                (), f"Configured site override '{override}' is not present in the source file.",
            ))
            continue

        # Aliases are ordered business rules. The first configured alias present
        # in the file wins. This preserves proven priorities such as
        # ADMS-SLD LINK -> RMU可关联 -> 环网柜ID while still refusing duplicate
        # physical columns with the *same* normalized header.
        actual = None
        for alias in spec.aliases:
            candidates = normalized_actual.get(normalize_header(alias), [])
            if len(candidates) > 1:
                mappings.append(FieldMapping(
                    spec.key, spec.label, None, spec.required, MappingKind.AMBIGUOUS,
                    tuple(candidates), f"Header '{alias}' occurs more than once.",
                ))
                actual = "__AMBIGUOUS__"
                break
            if len(candidates) == 1:
                actual = candidates[0]
                break
        if actual == "__AMBIGUOUS__":
            continue
        if actual is None:
            mappings.append(FieldMapping(spec.key, spec.label, None, spec.required, MappingKind.MISSING))
            continue
        used.add(actual)
        kind = MappingKind.EXACT if normalize_header(actual) == normalize_header(spec.preferred_header) else MappingKind.ALIAS
        mappings.append(FieldMapping(spec.key, spec.label, actual, spec.required, kind))

    ignored = tuple(header for header in actual_headers if header not in used)
    return SchemaValidationResult(schema, actual_headers, tuple(mappings), ignored)


def canonicalize_row(row: Mapping[str, object], validation: SchemaValidationResult) -> dict[str, object]:
    output: dict[str, object] = {}
    for mapping in validation.mappings:
        output[mapping.canonical_key] = row.get(mapping.actual_column) if mapping.actual_column else None
    return output


def canonicalize_rows(rows, validation: SchemaValidationResult) -> list[dict[str, object]]:
    return [canonicalize_row(row, validation) for row in rows]
