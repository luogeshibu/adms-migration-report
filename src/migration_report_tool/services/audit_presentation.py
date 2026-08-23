"""Human-readable presentation of immutable audit-log records.

The ``changes`` table deliberately stores stable internal field keys.  This
module translates those keys at presentation time so old audit rows immediately
benefit from improved UI wording without rewriting immutable history.
"""
from __future__ import annotations

from typing import Mapping

from ..config.column_schema import DATA_GROUPS
from ..config.sources import schema_for
from ..parsers import clean


_RMU_FIELD_LABELS: dict[str, str] = {}
for group_name, _color, columns in DATA_GROUPS:
    for key, label, _width in columns:
        # Include the source group when the plain label would otherwise lose the
        # business context (for example several different Feeder/RMU columns).
        if group_name in {"Index", "Remarks", "Resolution"}:
            display = label
        elif group_name == "Analysis":
            display = f"Analysis · {label}"
        else:
            display = f"{group_name} · {label}"
        _RMU_FIELD_LABELS[key] = display

_SPECIAL_FIELDS = {
    "rmu_review_status": "Review Status",
    "rmu_review_comment": "Manual Review Comment",
    "db_smart_review_status": "Review Status",
    "db_smart_comments": "Comments",
    "standard_reference": "STANDARD Reference",
}


def _source_type_from_record(record: str) -> str:
    text = clean(record)
    for prefix in ("SCHEMA:", "DISPLAY:"):
        if text.upper().startswith(prefix):
            return text[len(prefix):].strip()
    return ""


def audit_module(item: Mapping[str, object]) -> str:
    record = clean(item.get("rmu"))
    field = clean(item.get("field_name"))
    reason = clean(item.get("reason")).casefold()
    upper_record = record.upper()

    if upper_record.startswith("DBSMART:") or field.startswith("db_smart_") or "signal mapping" in reason:
        return "Signal Mapping Review"
    if upper_record == "STANDARD" or field == "standard_reference":
        return "Signal Mapping Review"
    if upper_record.startswith("SCHEMA:") or field.startswith("source_mapping."):
        return "Site Data Sources"
    if upper_record.startswith("DISPLAY:") or field.startswith("display_name."):
        return "Display Names"
    # Structured Resolution, optional RMU review, automatic RMU review resets,
    # and audited source-value corrections all belong to RMU Data Review.
    return "RMU Data Review"


def audit_record_label(item: Mapping[str, object]) -> str:
    record = clean(item.get("rmu"))
    upper = record.upper()
    if upper.startswith("DBSMART:"):
        value = record.split(":", 1)[1].strip()
        return f"RMU {value}" if value else "Signal Record"
    if upper.startswith("SCHEMA:") or upper.startswith("DISPLAY:"):
        source_type = record.split(":", 1)[1].strip()
        schema = schema_for(source_type)
        return schema.label if schema else source_type.replace("_", " ").upper()
    if upper == "STANDARD":
        return "IOA STANDARD"
    return f"RMU {record}" if record else "—"


def _schema_field_label(source_type: str, field_key: str) -> str:
    schema = schema_for(source_type)
    if not schema:
        return field_key.replace("_", " ").title()
    for spec in schema.fields:
        if clean(spec.key) == clean(field_key):
            return spec.label
    return field_key.replace("_", " ").title()


def audit_field_label(item: Mapping[str, object]) -> str:
    record = clean(item.get("rmu"))
    field = clean(item.get("field_name"))
    if field in _SPECIAL_FIELDS:
        return _SPECIAL_FIELDS[field]
    if field.startswith("resolution."):
        issue = field.split(".", 1)[1].strip().upper()
        return f"Resolution · {issue}" if issue else "Resolution"
    if field.startswith("source_mapping."):
        key = field.split(".", 1)[1].strip()
        label = _schema_field_label(_source_type_from_record(record), key)
        return f"Column Mapping · {label}"
    if field.startswith("display_name."):
        key = field.split(".", 1)[1].strip()
        label = _schema_field_label(_source_type_from_record(record), key)
        return f"Display Name · {label}"
    if field in _RMU_FIELD_LABELS:
        return _RMU_FIELD_LABELS[field]
    return field.replace("_", " ").replace(".", " · ").title() if field else "—"


def present_audit_item(item: Mapping[str, object]) -> dict[str, str]:
    """Return a business-facing view while preserving the immutable raw keys."""
    return {
        "id": clean(item.get("id")),
        "module": audit_module(item),
        "record": audit_record_label(item),
        "field": audit_field_label(item),
        "internal_field": clean(item.get("field_name")),
        "original_value": clean(item.get("old_value")),
        "new_value": clean(item.get("new_value")),
        "reason": clean(item.get("reason")),
        "modified_by": clean(item.get("modified_by")),
        "modified_at": clean(item.get("modified_at")),
    }
