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
    if not store:
        return set()
    root = store.config.get("hidden_source_fields", {}) or {}
    values = root.get(source_type, []) or []
    return {str(value).strip() for value in values if str(value).strip()}


def set_hidden_source_fields(store, source_type: str, field_keys, modified_by: str = "") -> None:
    if not store:
        return
    locked = system_logic_field_keys(source_type)
    cleaned = sorted({str(value).strip() for value in (field_keys or []) if str(value).strip()} - locked)
    root = store.config.setdefault("hidden_source_fields", {})
    before = sorted(get_hidden_source_fields(store, source_type))
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
            app_name = str((item or {}).get("display_name") or (item or {}).get("field_key") or "").strip()
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



def equipment_source_review_groups(store):
    """Return the universal five-source Equipment Data Review layout.

    Every visible App field in Source Mapping is a candidate review column.
    The fixed core columns keep their established keys/order, while additional
    built-in optional fields and USER App columns are appended using stable
    source-scoped keys.  Reviewer visibility is handled separately by the
    Columns dialog; this function only defines which App fields exist.
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
    hidden_by_source = {
        source_type: get_hidden_source_fields(store, source_type)
        for source_type in source_by_group.values()
    }

    # Build a complete built-in field catalog.  Fields already represented by
    # the fixed universal grid retain their original review keys; the remaining
    # mapped App fields become dynamic source-scoped columns.
    builtin_by_group: dict[str, list[tuple[str, str, int]]] = {}
    field_by_review_key: dict[str, str] = {}
    for group_name, source_type in source_by_group.items():
        schema = schema_for(source_type)
        if schema is None:
            continue
        display_names = get_source_display_names(store, source_type)
        hidden = hidden_by_source.get(source_type, set())
        # Only treat fields as already present when their review key is actually
        # part of this source group's fixed base layout.  The binding catalog is
        # intentionally broader than the fixed grid (it also contains historical
        # optional fields such as Resolved Full Name), so using the whole binding
        # catalog here would incorrectly suppress those optional App fields.
        base_group = next((columns for name, _color, columns in base if name == group_name), ())
        base_review_keys = {column[0] for column in base_group}
        fixed_fields = {
            field_key
            for review_key, (bound_source, field_key) in EQUIPMENT_SOURCE_DISPLAY_BINDINGS.items()
            if bound_source == source_type and review_key in base_review_keys
        }
        for spec in schema.fields:
            if spec.key in hidden or spec.key in fixed_fields:
                continue
            review_key = equipment_review_column_key(source_type, spec.key)
            label = display_names.get(spec.key) or default_display_name(source_type, spec.key, spec.label)
            width = 180 if any(token in spec.key for token in ("name", "destination", "location", "reason")) else 130
            builtin_by_group.setdefault(group_name, []).append((review_key, label, width))
            field_by_review_key[review_key] = spec.key

    # Remove mapping-level hidden optional built-ins from the fixed core groups.
    filtered = []
    for group, color, columns in base:
        kept = []
        for column in columns:
            key = column[0]
            binding = EQUIPMENT_SOURCE_DISPLAY_BINDINGS.get(key)
            if binding and binding[1] in hidden_by_source.get(binding[0], set()):
                continue
            kept.append(column)
        filtered.append((group, color, tuple(kept)))
    base = filtered

    custom_by_group: dict[str, list[tuple[str, str, int]]] = {}
    custom_field_by_review_key: dict[str, str] = {}
    for group_name, source_type in source_by_group.items():
        try:
            fields = store.custom_source_fields(source_type)
        except Exception:
            fields = []
        for item in fields or []:
            field_key = str((item or {}).get("field_key") or "").strip()
            display_name = str((item or {}).get("display_name") or field_key).strip()
            if not field_key or not display_name:
                continue
            review_key = custom_review_column_key(source_type, field_key)
            custom_field_by_review_key[review_key] = field_key
            custom_by_group.setdefault(group_name, []).append((review_key, display_name, 130))

    resolved = []
    for group, color, columns in base:
        combined = list(columns) + list(builtin_by_group.get(group, ())) + list(custom_by_group.get(group, ()))
        source_type = source_by_group.get(group)
        order = get_source_column_order(store, source_type) if source_type else None
        if source_type:
            # Record fixed source bindings for ordering lookup as well.
            for review_key, binding in EQUIPMENT_SOURCE_DISPLAY_BINDINGS.items():
                if binding[0] == source_type:
                    field_by_review_key.setdefault(review_key, binding[1])
        if source_type and order:
            field_to_column: dict[str, tuple[str, str, int]] = {}
            for column in combined:
                review_key = column[0]
                field_key = field_by_review_key.get(review_key) or custom_field_by_review_key.get(review_key, "")
                if field_key and field_key not in field_to_column:
                    field_to_column[field_key] = column
            reordered = [field_to_column[key] for key in order if key in field_to_column]
            used = {column[0] for column in reordered}
            reordered.extend(column for column in combined if column[0] not in used)
            combined = reordered
        resolved.append((group, color, tuple(combined)))
    return tuple(resolved)

def validation_summary(result) -> str:
    if result is None:
        return "N/A"
    if result.level == SchemaLevel.ERROR:
        return f"ERROR ({len(result.errors)})"
    if result.level == SchemaLevel.WARNING:
        return f"WARNING ({len(result.warnings)})"
    return "READY"
