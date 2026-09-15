"""Business-module to source-table relationships shown by Site Repository.

The same physical table may intentionally appear in more than one module.  This
is a dependency view, not a de-duplicated file inventory.  Keeping the
relationship explicit makes it obvious which tables feed each review module.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleTableRef:
    source_type: str
    label: str
    role: str
    expected_name: str  # recommended discovery filename only; manual mapped filenames may be arbitrary
    # Canonical App fields actually consumed by this module from this table.
    # Keeping this explicit lets Site Data Sources explain the dependency and
    # mapping without exposing unrelated columns from the same physical file.
    field_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleSourceGroup:
    key: str
    label: str
    description: str
    tables: tuple[ModuleTableRef, ...]


MODULE_SOURCE_GROUPS: tuple[ModuleSourceGroup, ...] = (
    ModuleSourceGroup(
        "rmu_review",
        "Equipment Data Review",
        "Equipment Data Review supports any number of configured CSV/XLSX/XLSM source tables. Each site chooses its own source files, Key / Index fields, comparison fields and visible columns while keeping the existing Analysis, Review Status, Resolution, Comments and Needs Action lifecycle workflow.",
        (
            ModuleTableRef(
                "se_list", "SE Equipment", "RMU / feeder / SMART reference", "SE.xlsx",
                ("station", "feeder", "rmu", "smart", "oh_ug", "rmu_type", "ip"),
            ),
            ModuleTableRef(
                "zenon_sld", "ZENON SLD", "Authoritative all-equipment graphical inventory for RMU and every other detected DeviceType", "ZENON-SLD.csv",
                (
                    "device_type", "rmu", "feeder", "cabinet_type", "screen_name", "smart",
                    "duplicate_count", "warning", "ip",
                    "script_version", "xml_file", "destination_name", "display_name",
                    "resolved_full_name", "full_destination",
                    "raw_substitute_destination", "link_name", "substitute_source",
                    "vendor", "name_source", "name_status", "confidence",
                    "variable_root_match", "classification_reason", "element",
                    "element_name", "start_x", "start_y"
                ),
            ),
            ModuleTableRef(
                "zenon_db", "ZENON DB", "Device / driver / communication data", "ZENON-DB.csv",
                ("rmu", "feeder", "brand", "rmu_type", "nop", "smart", "vip", "function_location",
                 "ip", "port", "link_address", "link_address_size", "cot_size", "coa_size", "ioa_size",
                 "t1", "t2", "t3", "k_value", "w_value", "net_address"),
            ),
            ModuleTableRef(
                "adms_db", "ADMS DB", "ADMS migration / channel / optional SMART data", "ADMS-DB.csv",
                ("rmu", "gss_fid", "y1", "y2", "y3", "y4", "q1", "q2", "rmu_type", "smart", "channel_ip", "channel_port"),
            ),
            ModuleTableRef(
                "adms_sld", "ADMS SLD", "ADMS all-equipment main-device inventory / symbol-validation reference", "ADMS-SLD.xlsx",
                (
                    "rmu", "device_type", "rmu_type", "smart", "feeder", "ip",
                    "g_file", "fac_id", "is_smart", "smart_source", "device_form",
                    "parent_rmu", "device_subtype", "profile_device_type", "xml_element",
                    "element_id", "key_id", "key_name", "p_name_string", "standard_file",
                    "standard_devref", "actual_devref", "symbol_validation", "validation_issue",
                    "name_source", "name_confidence", "display_label", "display_label_distance",
                    "quality_status", "x", "y", "w", "h",
                ),
            ),
        ),
    ),
    ModuleSourceGroup(
        "signal_mapping",
        "Signal Mapping Review",
        "Signal review assembled from the site IOA table, ADMS SLD cabinet type and the active application STANDARD reference.",
        (
            ModuleTableRef(
                "ioa", "ZENON-ADMS IOA", "ZENON ↔ ADMS signal mapping", "ZENON-ADMS-IOA.csv",
                ("rmu", "zenon_gss_fid", "zenon_signal_name", "zenon_dot_no",
                 "adms_gss_fid", "adms_signal_name", "adms_dot_no"),
            ),
            ModuleTableRef("adms_sld", "ADMS SLD", "Shared RMU type reference", "ADMS-SLD.csv", ("rmu", "rmu_type")),
            ModuleTableRef("standard_reference", "IOA STANDARD", "Application reference table", "IOA STANDARD.xlsx", ("type", "ioa", "name")),
        ),
    ),
)

MODULE_BY_KEY = {module.key: module for module in MODULE_SOURCE_GROUPS}
