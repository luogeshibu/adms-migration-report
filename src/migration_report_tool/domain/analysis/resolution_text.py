"""Customer-facing text for structured RMU resolution decisions.

The automatic Analysis result remains unchanged.  This module only turns a
reviewer's structured decision into a complete, stable description that can be
shown in the desktop UI and frozen into formal sign-off reports.
"""
from __future__ import annotations

from ...parsers import clean

FIELD_LABELS = {
    "NAME": "RMU name",
    "FEEDER": "feeder assignment",
    "SMART": "SMART classification",
    "TYPE": "RMU type",
    "IP": "communication IP",
    "LINK": "ADMS SLD association",
}


def field_label(field: str, equipment_type: str = "RMU") -> str:
    token = clean(field).upper()
    dtype = clean(equipment_type).upper() or "RMU"
    if dtype != "RMU":
        if token == "NAME":
            return "equipment name"
        if token == "TYPE":
            return "equipment type / subtype"
    return FIELD_LABELS.get(token, clean(field).replace("_", " ").lower() or "item")


def build_resolution_description(
    *,
    rmu: str,
    field: str,
    decision_type: str,
    selected_source: str = "",
    selected_value: str = "",
    normalized_value: str = "",
    equipment_type: str = "RMU",
) -> str:
    """Return a complete sign-off-ready sentence for one structured decision."""
    rmu = clean(rmu) or "-"
    field = clean(field).upper()
    decision = clean(decision_type).upper()
    source = clean(selected_source) or "selected source"
    raw_value = clean(selected_value)
    normalized = clean(normalized_value)
    agreed_value = raw_value or normalized or "<blank>"
    dtype = clean(equipment_type).upper() or "RMU"
    label = field_label(field, dtype)
    entity = f"RMU {rmu}" if dtype == "RMU" else f"{dtype} equipment {rmu}"

    if decision == "USE_SOURCE":
        if field == "FEEDER":
            return (
                f"Use {source} feeder value '{agreed_value}' as the approved feeder assignment for {entity}. "
                "Align the feeder value in the other affected source(s) to this assignment, then re-run Validation and confirm the FEEDER check is TRUE."
            )
        if field == "NAME":
            return (
                f"Use {source} RMU name '{agreed_value}' as the approved name for {entity}. "
                "Align the equipment name in the other affected source(s) to this value, then re-run Validation and confirm the NAME check is TRUE."
            )
        if field == "SMART":
            return (
                f"Use {source} SMART value '{agreed_value}' as the approved SMART/NORMAL classification for {entity}. "
                "Align the classification in the other affected source(s), then re-run Validation and confirm the SMART check is TRUE."
            )
        if field == "TYPE":
            return (
                f"Use {source} type value '{agreed_value}' as the approved type for {entity}. "
                "Align the equipment type in the other affected source(s) to this value, then re-run Validation and confirm the TYPE check is TRUE."
            )
        if field == "IP":
            return (
                f"Use {source} IP value '{agreed_value}' as the approved communication IP for {entity}. "
                "Align the IP in the other affected source(s) to this value, then re-run Validation and confirm the IP check is TRUE."
            )
        return (
            f"Use {source} value '{agreed_value}' as the approved {label} for {entity}. "
            f"Align the other affected source(s) to this value, then re-run Validation and confirm the {field or 'Analysis'} check is TRUE."
        )

    if decision == "NEEDS_ACTION":
        return (
            f"Further corrective action is required for the {label} issue on {entity}. "
            "Keep this item in Needs Action until the affected source data or model association is corrected, then re-run Validation before closure."
        )

    if decision == "ACCEPT_EXCEPTION":
        return (
            f"Accept the current {label} inconsistency for {entity} as an approved exception for this revision. "
            "No source value is changed by this decision; retain the existing values and record the exception in the formal sign-off report."
        )

    if decision == "OTHER":
        comment = clean(selected_value)
        if comment:
            return f"Other agreed resolution / comment for the {label} issue on {entity}: {comment}"
        return f"Enter the agreed custom resolution / comment for the {label} issue on {entity}."

    return f"The {label} issue on {entity} remains unresolved and requires a review decision before closure."


def resolution_display_text(record: dict) -> str:
    """Read a persisted description, with backward-compatible generation."""
    stored = clean((record or {}).get("decision_description"))
    if stored:
        return stored
    return build_resolution_description(
        rmu=clean((record or {}).get("rmu")),
        field=clean((record or {}).get("analysis_field")),
        decision_type=clean((record or {}).get("decision_type")),
        selected_source=clean((record or {}).get("selected_source")),
        selected_value=clean((record or {}).get("selected_value")),
        normalized_value=clean((record or {}).get("normalized_value")),
    )


def compact_resolution_text(record: dict) -> str:
    """Compact but complete-enough UI text used in the RMU review grid."""
    field = clean((record or {}).get("analysis_field")).upper()
    decision = clean((record or {}).get("decision_type")).upper()
    source = clean((record or {}).get("selected_source"))
    value = clean((record or {}).get("selected_value")) or clean((record or {}).get("normalized_value"))
    if decision == "USE_SOURCE":
        prefix = f"{field}: Adopt {source or 'selected source'}"
        if value:
            prefix += f" '{value}'"
        return prefix + " as the agreed value; align affected source(s) and re-run Validation."
    if decision == "NEEDS_ACTION":
        return f"{field}: Corrective action required; keep open until corrected and revalidated."
    if decision == "ACCEPT_EXCEPTION":
        return f"{field}: Approved exception; retain current values and include the exception in sign-off."
    if decision == "OTHER":
        comment = clean((record or {}).get("selected_value")) or clean((record or {}).get("decision_description"))
        return f"{field}: Other - {comment}" if comment else f"{field}: Other custom resolution."
    return f"{field}: Unresolved."
