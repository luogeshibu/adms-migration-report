"""Application service for source-schema validation, mapping and display labels."""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Mapping, Sequence

from ..config.sources import schema_for
from ..domain.schema import BLANK_OVERRIDE_TOKEN, MappingKind, SchemaLevel, decode_manual_override, is_manual_override
from ..infrastructure.parsers import validate_source_file
from ..infrastructure.database.global_settings_store import (
    source_display_names as global_source_display_names,
    replace_source_display_names as replace_global_source_display_names,
    source_column_order as global_source_column_order,
    replace_source_column_order as replace_global_source_column_order,
    source_field_overrides as global_source_field_overrides,
    replace_source_field_overrides as replace_global_source_field_overrides,
    ensure_source_field_overrides as ensure_global_source_field_overrides,
    source_hidden_fields as global_source_hidden_fields,
    replace_source_hidden_fields as replace_global_source_hidden_fields,
)


# Presentation bindings intentionally sit outside the canonical parser schema.
# The left-hand key is a report/UI column key; the right-hand tuple identifies
# the source contract whose user-editable Display Name should be shown.
RMU_REVIEW_DISPLAY_BINDINGS: dict[str, tuple[str, str]] = {
    "se_station": ("se_list", "station"),
    "se_feeder": ("se_list", "feeder"),
    "se_rmu": ("se_list", "rmu"),
    "se_smart": ("se_list", "smart"),
    "se_oh_ug": ("se_list", "oh_ug"),
    "zdb_feeder": ("zenon_db", "feeder"),
    "zdb_rmu": ("zenon_db", "rmu"),
    "zdb_brand": ("zenon_db", "brand"),
    "zdb_device": ("zenon_db", "rmu_type"),
    "zdb_nop": ("zenon_db", "nop"),
    "zdb_smart": ("zenon_db", "smart"),
    "zdb_vip": ("zenon_db", "vip"),
    "zdb_function_location": ("zenon_db", "function_location"),
    "driver_ip": ("zenon_db", "ip"),
    "driver_port": ("zenon_db", "port"),
    "driver_link_address": ("zenon_db", "link_address"),
    "driver_link_address_size": ("zenon_db", "link_address_size"),
    "driver_cot_size": ("zenon_db", "cot_size"),
    "driver_coa_size": ("zenon_db", "coa_size"),
    "driver_ioa_size": ("zenon_db", "ioa_size"),
    "driver_t1": ("zenon_db", "t1"),
    "driver_t2": ("zenon_db", "t2"),
    "driver_t3": ("zenon_db", "t3"),
    "driver_k": ("zenon_db", "k_value"),
    "driver_w": ("zenon_db", "w_value"),
    "driver_net_address": ("zenon_db", "net_address"),
    "zsld_device_type": ("zenon_sld", "device_type"),
    "zsld_screen_name": ("zenon_sld", "screen_name"),
    "zsld_feeder": ("zenon_sld", "feeder"),
    "zsld_rmu": ("zenon_sld", "rmu"),
    "zsld_type": ("zenon_sld", "cabinet_type"),
    "zsld_smart": ("zenon_sld", "smart"),
    "adb_rmu": ("adms_db", "rmu"),
    "adb_gss_fid": ("adms_db", "gss_fid"),
    "adb_y1": ("adms_db", "y1"),
    "adb_y2": ("adms_db", "y2"),
    "adb_y3": ("adms_db", "y3"),
    "adb_y4": ("adms_db", "y4"),
    "adb_q1": ("adms_db", "q1"),
    "adb_q2": ("adms_db", "q2"),
    "adb_type": ("adms_db", "rmu_type"),
    "adb_smart": ("adms_db", "smart"),
    "adms_channel_ip": ("adms_db", "channel_ip"),
    "adms_channel_port": ("adms_db", "channel_port"),
    "asld_rmu": ("adms_sld", "rmu"),
    "asld_type": ("adms_sld", "rmu_type"),
    "asld_smart": ("adms_sld", "smart"),
    "asld_link": ("adms_sld", "link"),
}



# Display-name bindings for the generic five-source Equipment Data Review view.
# These reuse the same canonical source fields as the RMU profile, but the
# visible labels are equipment-neutral so CB/LBS/FUSE/REC/TRANSFORMER and future
# classes can use the exact same physical source mappings.
EQUIPMENT_SOURCE_DISPLAY_BINDINGS: dict[str, tuple[str, str]] = {
    "eq_se_station": ("se_list", "station"),
    "eq_se_feeder": ("se_list", "feeder"),
    "eq_se_rmu": ("se_list", "rmu"),
    "eq_se_device_type": ("se_list", "device_type"),
    "eq_se_type": ("se_list", "rmu_type"),
    "eq_se_smart": ("se_list", "smart"),
    "eq_se_oh_ug": ("se_list", "oh_ug"),
    "eq_se_ip": ("se_list", "ip"),
    "eq_zdb_feeder": ("zenon_db", "feeder"),
    "eq_zdb_rmu": ("zenon_db", "rmu"),
    "eq_zdb_brand": ("zenon_db", "brand"),
    "eq_zdb_device_type": ("zenon_db", "device_type"),
    "eq_zdb_type": ("zenon_db", "rmu_type"),
    "eq_zdb_smart": ("zenon_db", "smart"),
    "eq_zdb_ip": ("zenon_db", "ip"),
    "eq_zdb_port": ("zenon_db", "port"),
    "eq_zdb_function_location": ("zenon_db", "function_location"),
    "eq_zsld_rmu": ("zenon_sld", "rmu"),
    "eq_zsld_device_type": ("zenon_sld", "device_type"),
    "eq_zsld_feeder": ("zenon_sld", "feeder"),
    "eq_zsld_type": ("zenon_sld", "cabinet_type"),
    "eq_zsld_screen": ("zenon_sld", "screen_name"),
    "eq_zsld_smart": ("zenon_sld", "smart"),
    "eq_zsld_ip": ("zenon_sld", "ip"),
    "eq_zsld_name_status": ("zenon_sld", "name_status"),
    "eq_zsld_confidence": ("zenon_sld", "confidence"),
    "eq_zsld_resolved_full_name": ("zenon_sld", "resolved_full_name"),
    "eq_zsld_element_name": ("zenon_sld", "element_name"),
    "eq_zsld_classification_reason": ("zenon_sld", "classification_reason"),
    "eq_zsld_warning": ("zenon_sld", "warning"),
    "eq_adb_rmu": ("adms_db", "rmu"),
    "eq_adb_feeder": ("adms_db", "gss_fid"),
    "eq_adb_device_type": ("adms_db", "device_type"),
    "eq_adb_type": ("adms_db", "rmu_type"),
    "eq_adb_smart": ("adms_db", "smart"),
    "eq_adb_ip": ("adms_db", "channel_ip"),
    "eq_adb_port": ("adms_db", "channel_port"),
    "eq_asld_rmu": ("adms_sld", "rmu"),
    "eq_asld_feeder": ("adms_sld", "feeder"),
    "eq_asld_type": ("adms_sld", "rmu_type"),
    "eq_asld_device_type": ("adms_sld", "device_type"),
    "eq_asld_smart": ("adms_sld", "smart"),
    "eq_asld_ip": ("adms_sld", "ip"),
}

# Stable reverse lookup for the universal Equipment Data Review.  Built-in
# fields already present in the fixed core layout keep their historical review
# keys; every other built-in App field receives a deterministic source-scoped
# key so it can be exposed in Columns without changing business logic.
EQUIPMENT_REVIEW_KEY_BY_SOURCE_FIELD: dict[tuple[str, str], str] = {
    binding: review_key for review_key, binding in EQUIPMENT_SOURCE_DISPLAY_BINDINGS.items()
}


def source_review_column_key(source_type: str, field_key: str) -> str:
    safe_source = str(source_type or "").strip().lower().replace("-", "_")
    safe_field = str(field_key or "").strip().lower().replace("-", "_")
    return f"source__{safe_source}__{safe_field}"


def equipment_review_column_key(source_type: str, field_key: str) -> str:
    """Return the stable UI/data key for one built-in source App field."""
    source_type = str(source_type or "").strip()
    field_key = str(field_key or "").strip()
    return EQUIPMENT_REVIEW_KEY_BY_SOURCE_FIELD.get(
        (source_type, field_key), source_review_column_key(source_type, field_key)
    )


SIGNAL_REVIEW_DISPLAY_BINDINGS: dict[str, tuple[str, str]] = {
    "rmu_no": ("ioa", "rmu"),
    "rmu_type": ("adms_sld", "rmu_type"),
    "zenon_gss_fid": ("ioa", "zenon_gss_fid"),
    "zenon_signal_name": ("ioa", "zenon_signal_name"),
    "zenon_dot_no": ("ioa", "zenon_dot_no"),
    "adms_gss_fid": ("ioa", "adms_gss_fid"),
    "adms_signal_name": ("ioa", "adms_signal_name"),
    "adms_dot_no": ("ioa", "adms_dot_no"),
    "standard_signal_name": ("standard_reference", "name"),
    "standard_dot_no": ("standard_reference", "ioa"),
}




# Built-in fields that participate in current application business logic.
# These fields are protected in Source Mapping.  Other built-in presentation
# fields may be hidden/restored by the user without changing parsing or
# validation algorithms.
#
# IMPORTANT: the historical internal key ``rmu`` is retained for database and
# project compatibility, but for equipment sources its canonical SYSTEM meaning
# is **Equipment Name / Record Identity**, not "RMU".  User-facing SYSTEM
# mapping UI must use the canonical FieldSpec label rather than legacy review
# presentation labels.
SYSTEM_LOGIC_FIELD_KEYS: dict[str, set[str]] = {
    "se_list": {"rmu", "device_type", "feeder", "smart", "rmu_type", "ip"},
    "zenon_db": {"rmu", "device_type", "feeder", "rmu_type", "smart", "ip", "port"},
    "zenon_sld": {"device_type", "rmu", "feeder", "cabinet_type", "smart", "duplicate_count", "ip"},
    "adms_db": {"rmu", "device_type", "gss_fid", "rmu_type", "smart", "channel_ip", "channel_port"},
    "adms_sld": {"rmu", "device_type", "rmu_type", "smart", "feeder", "ip"},
    # Signal Mapping depends on the complete IOA and STANDARD contracts.
    "ioa": {"rmu", "zenon_gss_fid", "zenon_signal_name", "zenon_dot_no",
            "adms_gss_fid", "adms_signal_name", "adms_dot_no"},
    "standard_reference": {"type", "ioa", "name"},
}


def system_logic_field_keys(source_type: str) -> set[str]:
    return set(SYSTEM_LOGIC_FIELD_KEYS.get(str(source_type or ""), set()))


def equipment_review_protected_column_keys(store=None) -> set[str]:
    """Columns that must stay visible in Equipment Data Review.

    The rule is deliberately derived from the same SYSTEM_LOGIC_FIELD_KEYS used
    by Source Mapping protection.  This prevents the review UI from hiding an
    input that currently feeds matching/Analysis/validation.  Computed identity,
    coverage and Analysis result columns are protected for the same reason.
    Optional/reference App fields and USER-added App columns remain reviewer
    controlled.
    """
    if store is not None:
        try:
            from .configurable_comparison_service import get_config, analysis_column_key
            configurable = get_config(store, bootstrap=False)
            if configurable.get("sources"):
                return {
                    "no", "rmu", "equipment_source_count", "equipment_missing_sources",
                    "remarks", "comments",
                    *{analysis_column_key(rule.get("id")) for rule in configurable.get("comparisons", []) if rule.get("id")},
                }
        except Exception:
            pass

    protected = {
        "no", "rmu", "equipment_device_type",
        "equipment_source_count", "equipment_missing_sources",
        "analysis_name", "analysis_feeder", "analysis_smart",
        "analysis_type", "analysis_ip",
    }
    for source_type, field_keys in SYSTEM_LOGIC_FIELD_KEYS.items():
        if source_type not in {"se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"}:
            continue
        for field_key in field_keys:
            protected.add(equipment_review_column_key(source_type, field_key))
    return protected


def get_hidden_source_fields(store, source_type: str) -> set[str]:
    """Return application-global source fields hidden from Equipment Data Review.

    v0.8.175 makes Map Fields visibility a true App-wide preference.  Mapping,
    App display names, Show/Hide and App-column order are shared by source type
    across every station.  A legacy per-site ``project.json`` visibility choice
    is promoted only when no global choice exists; after that, stale choices in
    other stations can never overwrite the global setting.

    Until any visibility preference exists, v0.8.171's compact default remains:
    optional fields start hidden while SYSTEM calculation fields stay visible.
    """
    source_type = str(source_type or "").strip()
    locked = system_logic_field_keys(source_type)

    try:
        global_values = global_source_hidden_fields(source_type)
    except Exception:
        global_values = None
    if global_values is not None:
        return {str(value).strip() for value in global_values if str(value).strip()} - locked

    # Upgrade path: an explicit old site-local visibility choice becomes the
    # initial global choice.  This is merge-once semantics: once global state
    # exists, opening another station with stale project.json cannot replace it.
    if store:
        root = store.config.get("hidden_source_fields", {}) or {}
        if source_type in root:
            values = {str(value).strip() for value in (root.get(source_type, []) or []) if str(value).strip()} - locked
            try:
                replace_global_source_hidden_fields(source_type, values, "migration")
            except Exception:
                pass
            return values

    if not store:
        return set()

    # No explicit visibility preference has ever been saved for this source.
    # Default-hide every optional built-in field plus every source-driven USER
    # field. SYSTEM calculation fields stay visible and cannot be hidden.
    schema = schema_for(source_type)
    hidden: set[str] = set()
    if schema is not None:
        hidden.update(spec.key for spec in schema.fields if spec.key not in locked)
    try:
        hidden.update(
            str(item.get("field_key") or "").strip()
            for item in (store.custom_source_fields(source_type) or [])
            if str(item.get("field_key") or "").strip()
        )
    except Exception:
        pass
    return hidden


def set_hidden_source_fields(store, source_type: str, field_keys, modified_by: str = "") -> None:
    """Save Show/Hide globally while keeping the current project's legacy copy.

    The global settings database is authoritative.  Updating the current site's
    project.json is only for backward compatibility/audit safety; other station
    databases do not need to be rewritten because they read the shared setting
    on demand.
    """
    source_type = str(source_type or "").strip()
    locked = system_logic_field_keys(source_type)
    cleaned = sorted({str(value).strip() for value in (field_keys or []) if str(value).strip()} - locked)
    before = sorted(get_hidden_source_fields(store, source_type))

    replace_global_source_hidden_fields(source_type, cleaned, modified_by)

    if store:
        root = store.config.setdefault("hidden_source_fields", {})
        root[source_type] = cleaned
        store.save_config()
        if before != cleaned and hasattr(store, "record_schema_mapping_change"):
            store.record_schema_mapping_change(
                source_type,
                {"hidden_optional_fields": before},
                {"hidden_optional_fields": cleaned},
                modified_by,
            )


def get_source_column_order(store, source_type: str) -> list[str] | None:
    """Application-wide display order for one source table.

    ``store`` is accepted for symmetry with the other schema-service helpers;
    ordering is presentation metadata and is intentionally not stored in a
    site's project database.
    """
    return global_source_column_order(source_type)


def set_source_column_order(store, source_type: str, field_keys, modified_by: str = "") -> None:
    """Persist display order without changing source mapping or business logic."""
    replace_global_source_column_order(source_type, field_keys, modified_by)



def get_resolved_source_mappings(store, source_type: str) -> dict[str, str]:
    """Return the last live App-field -> physical-column resolution.

    Auto mappings are resolved from the real source header only during an
    explicit Refresh/Validation/Map Fields action. Persisting that resolution
    keeps Site Data Sources informative during fast site switching without
    reopening every CSV/XLSX file.
    """
    if not store:
        return {}
    root = store.config.get("resolved_source_mappings", {}) or {}
    return {str(k): str(v).strip() for k, v in dict(root.get(source_type, {}) or {}).items() if str(v).strip()}


def set_resolved_source_mappings(store, source_type: str, mappings: Mapping[str, str]) -> None:
    if not store:
        return
    cleaned = {str(k): str(v).strip() for k, v in dict(mappings or {}).items() if str(v).strip()}
    root = store.config.setdefault("resolved_source_mappings", {})
    if dict(root.get(source_type, {}) or {}) == cleaned:
        return
    root[source_type] = cleaned
    store.save_config()


def module_field_mapping_lines(module_key: str, source_type: str, store, validation=None) -> list[str]:
    """Describe only the source fields actually consumed by one App module.

    The returned text is intentionally business-facing: ``App Column ← Source
    Field``.  It never invents a fallback from another table. Missing mappings
    remain ``—`` so reviewers can see that the physical file does not provide
    the field.
    """
    from ..config.source_modules import MODULE_BY_KEY

    module = MODULE_BY_KEY.get(str(module_key or ""))
    ref = next((r for r in module.tables if r.source_type == source_type), None) if module else None
    schema = schema_for(source_type)
    if ref is None or schema is None:
        return []

    specs = {spec.key: spec for spec in schema.fields}
    hidden = get_hidden_source_fields(store, source_type)
    display_names = get_source_display_names(store, source_type)
    overrides = get_source_overrides(store, source_type)
    resolved = get_resolved_source_mappings(store, source_type)
    live = getattr(validation, "mapping_by_key", {}) if validation is not None else {}

    lines: list[str] = []
    field_keys = [key for key in ref.field_keys if key in specs]
    preferred_order = get_source_column_order(store, source_type) or []
    if preferred_order:
        ordered = [key for key in preferred_order if key in field_keys]
        ordered.extend(key for key in field_keys if key not in ordered)
        field_keys = ordered
    for key in field_keys:
        if key in hidden:
            continue
        spec = specs.get(key)
        if spec is None:
            continue
        app_name = display_names.get(key, default_display_name(source_type, key, spec.label)) or spec.label
        mapping = live.get(key) if isinstance(live, dict) else None
        explicit = str(overrides.get(key) or "").strip()
        if getattr(mapping, "kind", None) == MappingKind.BLANK or explicit == BLANK_OVERRIDE_TOKEN:
            actual = ""
        else:
            actual = str(getattr(mapping, "actual_column", "") or "").strip()
            if not actual:
                explicit_display = decode_manual_override(explicit) if is_manual_override(explicit) else explicit
                actual = str(explicit_display or resolved.get(key) or "").strip()
        lines.append(f"{app_name} ← {actual or '—'}")

    # Project-added RMU columns are visible reference fields in RMU Data Review.
    if module_key == "rmu_review":
        try:
            custom = store.custom_source_fields(source_type) if store else []
        except Exception:
            custom = []
        for item in custom or []:
            field_key = str((item or {}).get("field_key") or "").strip()
            if field_key in hidden:
                continue
            app_name = str((item or {}).get("display_name") or field_key).strip()
            actual = str((item or {}).get("actual_column") or "").strip()
            if app_name:
                lines.append(f"{app_name} ← {actual or '—'}")
    return lines

def get_source_overrides(store, source_type: str) -> dict[str, str]:
    """Return application-global explicit Map Fields selections.

    ``store`` is retained for compatibility and as a legacy fallback. Opening an
    older project promotes its site-local choices merge-only into global settings
    without deleting or rewriting the old project.json values.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return {}
    try:
        global_values = dict(global_source_field_overrides(source_type) or {})
    except Exception:
        global_values = {}
    if global_values:
        return global_values
    if not store:
        return {}
    legacy = dict((store.config.get("source_column_overrides", {}) or {}).get(source_type, {}) or {})
    if legacy:
        try:
            ensure_global_source_field_overrides(source_type, legacy, "migration")
            promoted = dict(global_source_field_overrides(source_type) or {})
            if promoted:
                return promoted
        except Exception:
            pass
    return legacy


def set_source_overrides(store, source_type: str, overrides: dict[str, str], modified_by: str = "") -> None:
    """Save explicit Source Field selections globally for every station.

    The current project's old project.json copy is also updated for backward
    compatibility/audit safety, but it is no longer the authoritative mapping.
    """
    source_type = str(source_type or "").strip()
    before = get_source_overrides(store, source_type)
    cleaned = {str(k).strip(): str(v).strip() for k, v in dict(overrides or {}).items() if str(k).strip() and str(v).strip()}
    replace_global_source_field_overrides(source_type, cleaned, modified_by)
    if store:
        root = store.config.setdefault("source_column_overrides", {})
        root[source_type] = cleaned
        store.save_config()
        if before != cleaned and hasattr(store, "record_schema_mapping_change"):
            store.record_schema_mapping_change(source_type, before, cleaned, modified_by)


@lru_cache(maxsize=1)
def _presentation_default_labels() -> dict[tuple[str, str], str]:
    """Resolve the built-in App header for each source field.

    Canonical/System Field labels describe business meaning.  Review-table
    labels are presentation defaults and are intentionally allowed to differ
    (for example ZENON DB ``RMU Type`` is displayed as ``Device`` because the
    current source column is DEVICE).
    """
    from ..config.column_schema import COMPARISON_GROUPS
    from ..domain.mapping.signal_mapping import SIGNAL_MAPPING_GROUPS

    comparison_labels = {key: label for _g, _c, cols in COMPARISON_GROUPS for key, label, _w in cols}
    signal_labels = {key: label for _g, _c, cols in SIGNAL_MAPPING_GROUPS for key, label, _w in cols}
    output: dict[tuple[str, str], str] = {}
    for report_key, binding in RMU_REVIEW_DISPLAY_BINDINGS.items():
        if report_key in comparison_labels:
            output[binding] = comparison_labels[report_key]
    for report_key, binding in SIGNAL_REVIEW_DISPLAY_BINDINGS.items():
        if report_key in signal_labels:
            prior = output.get(binding)
            label = signal_labels[report_key]
            if prior and prior != label:
                raise RuntimeError(f"Conflicting display defaults for {binding}: {prior!r} vs {label!r}")
            output[binding] = label
    return output


def default_display_name(source_type: str, field_key: str, fallback: str = "") -> str:
    return _presentation_default_labels().get((str(source_type), str(field_key)), fallback) or fallback


def canonical_system_field_label(source_type: str, field_key: str, fallback: str = "") -> str:
    """Return the canonical business semantic shown in SYSTEM mapping UI.

    Presentation/App labels may intentionally mirror a physical header or a
    historical review-table name (for example ``RMU``).  SYSTEM assignments
    must not use those presentation aliases because the protected semantic is
    the generic record identity.  For equipment sources the legacy internal
    key ``rmu`` therefore renders as ``Equipment Name``.
    """
    schema = schema_for(str(source_type or ""))
    if schema is not None:
        spec = next((item for item in schema.fields if item.key == str(field_key or "")), None)
        if spec is not None and str(spec.label or "").strip():
            return str(spec.label).strip()
    return str(fallback or field_key or "").strip()


def get_source_display_names(store, source_type: str) -> dict[str, str]:
    """Return application-global Display Name overrides.

    ``store`` is accepted for API compatibility only.  Display Names are no
    longer site-local; one saved name applies to every site and formal export.
    """
    return dict(global_source_display_names(source_type) or {})


def set_source_display_names(store, source_type: str, names: dict[str, str], modified_by: str = "") -> None:
    """Persist application-global labels that differ from App presentation defaults."""
    schema = schema_for(source_type)
    if schema is None:
        return
    defaults = {
        field.key: default_display_name(source_type, field.key, field.label)
        for field in schema.fields
    }
    cleaned: dict[str, str] = {}
    for key, raw in (names or {}).items():
        key = str(key).strip()
        value = str(raw).strip()
        if key not in defaults or not value:
            continue
        if value != defaults[key]:
            cleaned[key] = value
    replace_global_source_display_names(source_type, cleaned, modified_by)


def field_display_name(store, source_type: str, field_key: str, fallback: str) -> str:
    default = default_display_name(source_type, field_key, fallback)
    return get_source_display_names(store, source_type).get(field_key, default) or default


def apply_display_names_to_groups(
    groups: Sequence[tuple[str, str, Sequence[tuple[str, str, int]]]],
    store,
    bindings: Mapping[str, tuple[str, str]],
):
    """Return group definitions with application-global labels applied."""
    source_types = {source_type for source_type, _field in bindings.values()}
    names_by_source = {source_type: get_source_display_names(store, source_type) for source_type in source_types}
    resolved = []
    for group, color, columns in groups:
        output_columns = []
        for key, label, width in columns:
            binding = bindings.get(key)
            if binding:
                source_type, field_key = binding
                label = names_by_source.get(source_type, {}).get(field_key, label) or label
            output_columns.append((key, label, width))
        resolved.append((group, color, tuple(output_columns)))
    return tuple(resolved)



# Project-local custom source fields can be exposed directly in RMU Data Review.
# The automatic Analysis contract remains fixed; these are presentation/reference
# columns only and never create NAME/FEEDER/SMART/TYPE/IP issues by themselves.
RMU_CUSTOM_GROUP_BY_SOURCE: dict[str, str] = {
    "se_list": "SE",
    "zenon_db": "ZENON DB",
    "zenon_sld": "ZENON SLD",
    "adms_db": "ADMS DB",
    "adms_sld": "ADMS SLD",
}


def custom_review_column_key(source_type: str, field_key: str) -> str:
    """Stable comparison-row key for a project-local mapped source field."""
    safe_source = str(source_type or "").strip().lower().replace("-", "_")
    safe_field = str(field_key or "").strip().lower().replace("-", "_")
    return f"custom__{safe_source}__{safe_field}"


def rmu_review_groups(store):
    """Return RMU review groups including global USER App columns and order.

    Column order is presentation-only and is stored by canonical App field key,
    never by the physical source-file ordinal position.  Therefore moving a CSV
    column, inserting a new source column, or reordering the physical file cannot
    change which business field is displayed or analyzed.
    """
    from ..config.column_schema import COMPARISON_GROUPS

    base = list(apply_display_names_to_groups(COMPARISON_GROUPS, store, RMU_REVIEW_DISPLAY_BINDINGS))
    if not store:
        return tuple(base)

    hidden_by_source = {
        source_type: get_hidden_source_fields(store, source_type)
        for source_type in RMU_CUSTOM_GROUP_BY_SOURCE
    }
    filtered_base = []
    for group, color, columns in base:
        kept = []
        for column in columns:
            key = column[0]
            binding = RMU_REVIEW_DISPLAY_BINDINGS.get(key)
            if binding:
                source_type, field_key = binding
                if field_key in hidden_by_source.get(source_type, set()):
                    continue
            kept.append(column)
        filtered_base.append((group, color, tuple(kept)))
    base = filtered_base

    custom_by_group: dict[str, list[tuple[str, str, int]]] = {}
    custom_field_by_review_key: dict[str, str] = {}
    for source_type, group_name in RMU_CUSTOM_GROUP_BY_SOURCE.items():
        try:
            fields = store.custom_source_fields(source_type)
        except Exception:
            fields = []
        for item in fields or []:
            field_key = str((item or {}).get("field_key") or "").strip()
            display_name = str((item or {}).get("display_name") or field_key).strip()
            if not field_key or not display_name:
                continue
            if field_key in hidden_by_source.get(source_type, set()):
                continue
            review_key = custom_review_column_key(source_type, field_key)
            custom_field_by_review_key[review_key] = field_key
            custom_by_group.setdefault(group_name, []).append((review_key, display_name, 130))

    source_by_group = {group_name: source_type for source_type, group_name in RMU_CUSTOM_GROUP_BY_SOURCE.items()}
    resolved = []
    for group, color, columns in base:
        combined = list(columns) + list(custom_by_group.get(group, ()))
        source_type = source_by_group.get(group)
        order = get_source_column_order(store, source_type) if source_type else None
        if source_type and order:
            field_to_column: dict[str, tuple[str, str, int]] = {}
            for column in combined:
                review_key = column[0]
                binding = RMU_REVIEW_DISPLAY_BINDINGS.get(review_key)
                field_key = ""
                if binding and binding[0] == source_type:
                    field_key = binding[1]
                elif review_key in custom_field_by_review_key:
                    field_key = custom_field_by_review_key[review_key]
                if field_key and field_key not in field_to_column:
                    field_to_column[field_key] = column

            reordered = [field_to_column[key] for key in order if key in field_to_column]
            used_review_keys = {column[0] for column in reordered}
            reordered.extend(column for column in combined if column[0] not in used_review_keys)
            combined = reordered
        resolved.append((group, color, tuple(combined)))
    return tuple(resolved)


def rmu_review_columns(store):
    return [column for _group, _color, columns in rmu_review_groups(store) for column in columns]

def inspect_source(source_type: str, path: Path | None, store=None):
    schema = schema_for(source_type)
    if schema is None:
        return None
    if not path:
        return None
    sheet_name = store.source_sheet_name(source_type) if store and Path(path).suffix.lower() in {".xlsx", ".xlsm"} and hasattr(store, "source_sheet_name") else ""
    return validate_source_file(source_type, Path(path), get_source_overrides(store, source_type), sheet_name=sheet_name or None)


def validate_required_source(source_type: str, path: Path, store=None):
    result = inspect_source(source_type, path, store)
    if result is not None and result.errors:
        from ..domain.schema import SchemaValidationError
        raise SchemaValidationError(result, Path(path).name)
    return result



def _live_review_source_validation(store, source_type: str):
    """Return cached validation for the active physical source used by Review.

    v0.8.168: Equipment Data Review must mirror the *current physical header*,
    not the static canonical schema.  Cache by file metadata + sheet + mapping
    overrides so repeated header/layout refreshes never repeatedly reopen a
    large workbook when nothing changed.
    """
    if not store or not hasattr(store, "source_path"):
        return None
    try:
        path = store.source_path(source_type)
    except Exception:
        path = None
    if not path:
        return None
    path = Path(path)
    if not path.exists():
        return None
    try:
        stat = path.stat()
        signature = (int(stat.st_mtime_ns), int(stat.st_size))
    except OSError:
        return None
    sheet_name = ""
    if path.suffix.lower() in {".xlsx", ".xlsm"} and hasattr(store, "source_sheet_name"):
        try:
            sheet_name = str(store.source_sheet_name(source_type) or "")
        except Exception:
            sheet_name = ""
    overrides = get_source_overrides(store, source_type)
    override_key = tuple(sorted((str(k), str(v)) for k, v in dict(overrides or {}).items()))
    cache_key = (str(source_type), str(path.resolve()), signature, sheet_name, override_key)
    cache = getattr(_live_review_source_validation, "_cache", None)
    if cache is None:
        cache = {}
        setattr(_live_review_source_validation, "_cache", cache)
    if cache_key in cache:
        return cache[cache_key]
    try:
        result = validate_source_file(
            source_type, path, overrides,
            sheet_name=sheet_name or None,
        )
    except Exception:
        result = None
    # Keep a small process-local cache.  Old metadata signatures are harmless,
    # but pruning avoids unbounded growth during repeated Excel saves.
    if len(cache) >= 64:
        cache.clear()
    cache[cache_key] = result
    return result


def _live_review_columns_for_source(store, source_type: str, validation):
    """Build exactly one review column for each mapped live physical header.

    This intentionally mirrors SourceMappingDialog's ownership rule: when one
    physical header satisfies multiple legacy aliases, SYSTEM/required semantics
    win and the header is rendered once.  Unmatched headers are represented by
    persisted source-driven USER fields after Map Fields has saved them.
    """
    schema = schema_for(source_type)
    if schema is None or validation is None:
        return []
    headers = [str(value).strip() for value in tuple(validation.headers or ()) if str(value).strip()]
    if not headers:
        return []
    header_lookup = {value.casefold(): value for value in headers}
    locked_fields = system_logic_field_keys(source_type)
    candidates: dict[str, list[tuple[int, int, str]]] = {}
    by_key = validation.mapping_by_key
    for index, spec in enumerate(schema.fields):
        mapping = by_key.get(spec.key)
        actual = str(getattr(mapping, "actual_column", "") or "").strip()
        hk = actual.casefold()
        if not hk or hk not in header_lookup:
            continue
        priority = 0
        if spec.key in locked_fields:
            priority += 100
        if spec.required:
            priority += 20
        if getattr(mapping, "kind", None) == MappingKind.EXACT:
            priority += 5
        candidates.setdefault(hk, []).append((-priority, index, spec.key))
    owners = {hk: sorted(values)[0][2] for hk, values in candidates.items()}

    try:
        custom_fields = [dict(item or {}) for item in (store.custom_source_fields(source_type) or [])]
    except Exception:
        custom_fields = []
    custom_by_header: dict[str, dict] = {}
    for item in custom_fields:
        actual = str(item.get("actual_column") or "").strip()
        if actual:
            custom_by_header.setdefault(actual.casefold(), item)

    display_names = get_source_display_names(store, source_type)
    hidden = get_hidden_source_fields(store, source_type)
    rows: list[tuple[str, str, str, int]] = []  # field_key, review_key, label, width
    for header in headers:
        hk = header.casefold()
        owner_key = owners.get(hk)
        if owner_key:
            # SYSTEM fields cannot be persisted hidden; keep the defensive check
            # here so an old config can never suppress a calculation input.
            if owner_key in hidden and owner_key not in locked_fields:
                continue
            review_key = equipment_review_column_key(source_type, owner_key)
            label = str(display_names.get(owner_key) or header).strip() or header
            width = 180 if any(token in owner_key for token in ("name", "destination", "location", "reason")) else 130
            rows.append((owner_key, review_key, label, width))
            continue

        item = custom_by_header.get(hk)
        if item is None:
            # A brand-new source header first appears in Map Fields.  It becomes
            # a review column after Save creates/persists its source-driven App
            # row; until then there is no row-data key to render safely.
            continue
        field_key = str(item.get("field_key") or "").strip()
        if not field_key or field_key in hidden:
            continue
        label = str(item.get("display_name") or header).strip() or header
        rows.append((field_key, custom_review_column_key(source_type, field_key), label, 130))

    order = get_source_column_order(store, source_type) or []
    if order:
        by_field = {field_key: row for field_key, *rest in rows for row in [(field_key, *rest)]}
        ordered = [by_field[key] for key in order if key in by_field]
        used = {row[0] for row in ordered}
        ordered.extend(row for row in rows if row[0] not in used)
        rows = ordered
    return [(review_key, label, width) for _field_key, review_key, label, width in rows]


def equipment_source_review_groups(store):
    # v0.8.178: once a site has the configurable comparison source layer, the
    # review grid is generated directly from that site's real files/rules.
    if store is not None:
        try:
            from .configurable_comparison_service import get_config, review_groups
            configurable = get_config(store, bootstrap=False)
            if configurable.get("sources"):
                return review_groups(store)
        except Exception:
            # Keep the historical five-source layout as a safety fallback so a
            # malformed in-progress configuration never prevents the project from opening.
            pass

    """Return the universal Equipment Data Review layout.

    v0.8.168 source groups are *physical-header driven*: for an active project,
    SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD show exactly the columns that
    exist in each current file, minus optional rows hidden in Map Fields.  A
    canonical SYSTEM field is forced visible only when its physical source row
    actually exists; missing physical fields never create phantom review columns.

    Index / Source Coverage / Analysis / Remarks / Resolution remain application
    columns and are not physical source rows.
    """
    from ..config.column_schema import EQUIPMENT_SOURCE_GROUPS

    base = list(apply_display_names_to_groups(
        EQUIPMENT_SOURCE_GROUPS, store, EQUIPMENT_SOURCE_DISPLAY_BINDINGS
    ))
    if not store:
        return tuple(base)

    source_by_group = {
        "SE": "se_list",
        "ZENON DB": "zenon_db",
        "ZENON SLD": "zenon_sld",
        "ADMS DB": "adms_db",
        "ADMS SLD": "adms_sld",
    }
    # Preserve the historical schema-only fallback for an empty/new ProjectStore
    # with no source files at all.  Once any physical source is active, the
    # review becomes source-faithful and missing source files contribute 0 cols.
    has_any_live_source = False
    if hasattr(store, "source_path"):
        for source_type in source_by_group.values():
            try:
                if store.source_path(source_type):
                    has_any_live_source = True
                    break
            except Exception:
                pass
    if not has_any_live_source:
        # Keep legacy schema catalog behavior for tooling/tests before a site has
        # loaded physical sources.  Source-driven behavior starts with real data.
        hidden_by_source = {
            source_type: get_hidden_source_fields(store, source_type)
            for source_type in source_by_group.values()
        }
        resolved = []
        for group, color, columns in base:
            source_type = source_by_group.get(group)
            if not source_type:
                resolved.append((group, color, columns))
                continue
            hidden = hidden_by_source.get(source_type, set())
            kept = []
            for column in columns:
                binding = EQUIPMENT_SOURCE_DISPLAY_BINDINGS.get(column[0])
                if binding and binding[1] in hidden:
                    continue
                kept.append(column)
            schema = schema_for(source_type)
            fixed_fields = {
                binding[1] for key, binding in EQUIPMENT_SOURCE_DISPLAY_BINDINGS.items()
                if binding[0] == source_type and any(c[0] == key for c in columns)
            }
            display_names = get_source_display_names(store, source_type)
            if schema is not None:
                for spec in schema.fields:
                    if spec.key in hidden or spec.key in fixed_fields:
                        continue
                    label = display_names.get(spec.key) or default_display_name(source_type, spec.key, spec.label)
                    width = 180 if any(token in spec.key for token in ("name", "destination", "location", "reason")) else 130
                    kept.append((equipment_review_column_key(source_type, spec.key), label, width))
            try:
                custom = store.custom_source_fields(source_type) or []
            except Exception:
                custom = []
            for item in custom:
                field_key = str((item or {}).get("field_key") or "").strip()
                label = str((item or {}).get("display_name") or field_key).strip()
                if field_key and label and field_key not in hidden:
                    kept.append((custom_review_column_key(source_type, field_key), label, 130))
            resolved.append((group, color, tuple(kept)))
        return tuple(resolved)

    resolved = []
    for group, color, columns in base:
        source_type = source_by_group.get(group)
        if not source_type:
            resolved.append((group, color, columns))
            continue
        validation = _live_review_source_validation(store, source_type)
        live_columns = _live_review_columns_for_source(store, source_type, validation)
        resolved.append((group, color, tuple(live_columns)))
    return tuple(resolved)

def validation_summary(result) -> str:
    if result is None:
        return "N/A"
    if result.level == SchemaLevel.ERROR:
        return f"ERROR ({len(result.errors)})"
    if result.level == SchemaLevel.WARNING:
        return f"WARNING ({len(result.warnings)})"
    return "READY"
