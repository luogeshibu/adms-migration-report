"""Application service for source-schema validation, mapping and display labels."""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Mapping, Sequence

from ..config.sources import schema_for
from ..domain.schema import SchemaLevel
from ..infrastructure.parsers import validate_source_file
from ..infrastructure.database.global_settings_store import (
    source_display_names as global_source_display_names,
    replace_source_display_names as replace_global_source_display_names,
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
    "zsld_screen_name": ("zenon_sld", "screen_name"),
    "zsld_feeder": ("zenon_sld", "feeder"),
    "zsld_rmu": ("zenon_sld", "rmu"),
    "zsld_type": ("zenon_sld", "cabinet_type"),
    "adb_rmu": ("adms_db", "rmu"),
    "adb_gss_fid": ("adms_db", "gss_fid"),
    "adb_y1": ("adms_db", "y1"),
    "adb_y2": ("adms_db", "y2"),
    "adb_y3": ("adms_db", "y3"),
    "adb_y4": ("adms_db", "y4"),
    "adb_q1": ("adms_db", "q1"),
    "adb_q2": ("adms_db", "q2"),
    "adb_type": ("adms_db", "rmu_type"),
    "adms_channel_ip": ("adms_db", "channel_ip"),
    "adms_channel_port": ("adms_db", "channel_port"),
    "asld_rmu": ("adms_sld", "rmu"),
    "asld_type": ("adms_sld", "rmu_type"),
    "asld_smart": ("adms_sld", "smart"),
    "asld_link": ("adms_sld", "link"),
}

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


def get_source_overrides(store, source_type: str) -> dict[str, str]:
    if not store:
        return {}
    return dict((store.config.get("source_column_overrides", {}) or {}).get(source_type, {}) or {})


def set_source_overrides(store, source_type: str, overrides: dict[str, str], modified_by: str = "") -> None:
    before = get_source_overrides(store, source_type)
    root = store.config.setdefault("source_column_overrides", {})
    cleaned = {str(k): str(v).strip() for k, v in overrides.items() if str(v).strip()}
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


def inspect_source(source_type: str, path: Path | None, store=None):
    schema = schema_for(source_type)
    if schema is None:
        return None
    if not path:
        return None
    return validate_source_file(source_type, Path(path), get_source_overrides(store, source_type))


def validate_required_source(source_type: str, path: Path, store=None):
    result = inspect_source(source_type, path, store)
    if result is not None and result.errors:
        from ..domain.schema import SchemaValidationError
        raise SchemaValidationError(result, Path(path).name)
    return result


def validation_summary(result) -> str:
    if result is None:
        return "N/A"
    if result.level == SchemaLevel.ERROR:
        return f"ERROR ({len(result.errors)})"
    if result.level == SchemaLevel.WARNING:
        return f"WARNING ({len(result.warnings)})"
    return "READY"
