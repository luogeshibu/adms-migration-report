"""Deterministic header matching with no semantic guessing."""
from __future__ import annotations

import re
from typing import Mapping, Sequence

BLANK_OVERRIDE_TOKEN = "__APP_EXPLICIT_BLANK__"
MANUAL_OVERRIDE_PREFIX = "__APP_MANUAL_SOURCE__::"


def encode_manual_override(actual_column: object) -> str:
    """Persist an explicit user-selected physical Source Field.

    The prefix distinguishes a deliberate current Manual choice from legacy
    raw overrides migrated from older releases.  Deliberate Manual mappings
    are authoritative; legacy raw values remain fallback-only so stale mappings
    cannot silently beat a real declared business header.
    """
    value = "" if actual_column is None else str(actual_column).strip()
    return f"{MANUAL_OVERRIDE_PREFIX}{value}" if value else ""


def is_manual_override(value: object) -> bool:
    return str(value or "").startswith(MANUAL_OVERRIDE_PREFIX)


def decode_manual_override(value: object) -> str:
    text = str(value or "")
    return text[len(MANUAL_OVERRIDE_PREFIX):].strip() if text.startswith(MANUAL_OVERRIDE_PREFIX) else text.strip()

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


def _physical_headers(headers: Sequence[object]) -> tuple[str, ...]:
    """Return physical headers in source order without collapsing duplicates.

    Business mapping is name-based, so column order is irrelevant.  Keeping
    duplicates is important: if a source contains the same business header
    twice we must report it as ambiguous instead of silently binding whichever
    physical position a CSV/XLSX reader happens to keep.
    """
    result: list[str] = []
    for header in headers:
        text = "" if header is None else str(header).replace("\ufeff", "").strip()
        if text:
            result.append(text)
    return tuple(result)


def resolve_schema(
    schema: SourceSchema,
    headers: Sequence[object],
    overrides: Mapping[str, str] | None = None,
) -> SchemaValidationResult:
    """Resolve physical columns to canonical business fields by header identity.

    Built-in/declared aliases are authoritative whenever they are present in the
    current file.  A persisted site override is therefore only a fallback for a
    genuinely non-standard header that is *not* covered by the built-in schema.

    This ordering is deliberate.  Older project configurations may contain a
    saved mapping to a column that happened to occupy a previous position (or
    to a legacy field such as ``NET_DESCRIPTION1``).  If a current file later
    contains the real business header, e.g. ``IP``, that named header must win
    even when the old override is still stored.  Reordering/inserting columns
    can therefore never redirect system analysis to another physical column.
    """
    overrides = {str(k): str(v) for k, v in (overrides or {}).items() if str(v).strip()}
    actual_headers = _physical_headers(headers)
    normalized_actual: dict[str, list[str]] = {}
    for header in actual_headers:
        normalized_actual.setdefault(normalize_header(header), []).append(header)

    mappings: list[FieldMapping] = []
    used: set[str] = set()
    for spec in schema.fields:
        override = overrides.get(spec.key, "").strip()

        # An explicit blank is a deliberate user choice, distinct from Auto.
        # It suppresses both automatic alias matching and any stale resolved
        # mapping so the canonical field is present with a None value.
        if override == BLANK_OVERRIDE_TOKEN:
            mappings.append(FieldMapping(
                spec.key, spec.label, None, spec.required, MappingKind.BLANK, (),
                "Explicitly left blank by the user. No physical Source Field is consumed.",
            ))
            continue

        # A v0.8.137+ Manual selection is an explicit current user decision and
        # therefore takes precedence over Auto aliases.  This is intentionally
        # different from legacy raw overrides below: old raw values remain
        # fallback-only so a stale historical mapping cannot silently redirect
        # system analysis when the real business header later appears.
        if is_manual_override(override):
            requested = decode_manual_override(override)
            candidates = normalized_actual.get(normalize_header(requested), [])
            if len(candidates) == 1:
                actual = candidates[0]
                used.add(actual)
                mappings.append(FieldMapping(
                    spec.key, spec.label, actual, spec.required, MappingKind.OVERRIDE, (),
                    f"Manual Source Field mapping is active: '{actual}'.",
                ))
                continue
            if len(candidates) > 1:
                mappings.append(FieldMapping(
                    spec.key, spec.label, None, spec.required, MappingKind.AMBIGUOUS,
                    tuple(candidates), f"Manual Source Field '{requested}' occurs more than once.",
                ))
                continue
            mappings.append(FieldMapping(
                spec.key, spec.label, None, spec.required, MappingKind.MISSING, (),
                f"Manual Source Field '{requested}' is not present in the source file.",
            ))
            continue

        # 1) Auto: the current physical header is authoritative. Resolve every
        # declared business alias by name before considering persisted legacy
        # overrides.  Alias order remains the business priority (IP before
        # IP_ADDRESS before NET_DESCRIPTION1, etc.).
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
        if actual is not None:
            used.add(actual)
            kind = MappingKind.EXACT if normalize_header(actual) == normalize_header(spec.preferred_header) else MappingKind.ALIAS
            message = ""
            if override and normalize_header(override) != normalize_header(actual):
                message = (
                    f"Saved site override '{override}' was ignored because the current source contains "
                    f"the declared business header '{actual}'. System logic binds by header name, not column position."
                )
            mappings.append(FieldMapping(spec.key, spec.label, actual, spec.required, kind, (), message))
            continue

        # 2) Only when no declared header exists may a site override supply a
        # confirmed non-standard physical column.  This preserves support for
        # site-specific exports without allowing stale mappings to override a
        # real/current business header.
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

        expected = tuple(str(alias).strip() for alias in spec.aliases if str(alias).strip())
        expected_text = ", ".join(expected)
        mappings.append(FieldMapping(
            spec.key, spec.label, None, spec.required, MappingKind.MISSING, (),
            ("Automatic mapping found no matching Source Field. "
             + (f"Expected header/alias: {expected_text}. " if expected_text else "")
             + "The App value will remain blank while Auto stays enabled."),
        ))

    ignored = tuple(header for header in actual_headers if header not in used)
    return SchemaValidationResult(schema, actual_headers, tuple(mappings), ignored)


def canonicalize_row(row: Mapping[str, object], validation: SchemaValidationResult) -> dict[str, object]:
    output: dict[str, object] = {}
    for mapping in validation.mappings:
        output[mapping.canonical_key] = row.get(mapping.actual_column) if mapping.actual_column else None
    return output


def canonicalize_rows(rows, validation: SchemaValidationResult) -> list[dict[str, object]]:
    return [canonicalize_row(row, validation) for row in rows]
