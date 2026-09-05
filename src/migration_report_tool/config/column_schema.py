"""Stable report schema, source definitions and application identity."""
from .. import __version__

APP_NAME = "NARI Saudi ADMS Migration Report"
APP_VERSION = __version__

# Stable source/review field schema.  The desktop App and formal RMU Data Review
# export use this data model; the old customer DATA worksheet is no longer the
# delivery layout.
DATA_GROUPS = [
    ("Index", "#FFFFFF", [("no", "No.", 55), ("rmu", "RMU", 90)]),
    ("SE", "#83D9D2", [
        ("se_station", "Station", 85), ("se_feeder", "Feeder", 110),
        ("se_rmu", "RMU", 90), ("se_smart", "SMART", 100), ("se_oh_ug", "OH / UG", 75),
    ]),
    # Every visible source group now corresponds to one physical source table.
    # Driver/communication fields are columns of ZENON-DB.csv, so they stay in
    # ZENON DB rather than being rendered as a separate pseudo-table.
    ("ZENON DB", "#E3F2D9", [
        ("zdb_feeder", "Feeder", 115), ("zdb_rmu", "RMU", 90), ("zdb_brand", "Brand", 100),
        ("zdb_device", "Device", 90), ("zdb_nop", "NOP", 65), ("zdb_smart", "SMART", 70),
        ("zdb_vip", "VIP", 80), ("zdb_function_location", "Function Location", 150),
        ("driver_ip", "IP", 120), ("driver_port", "PORT", 70), ("driver_link_address", "LINK_ADDRESS", 110),
        ("driver_link_address_size", "LINK_ADDRESS_SIZE", 130), ("driver_cot_size", "COT_SIZE", 85),
        ("driver_coa_size", "COA_SIZE", 85), ("driver_ioa_size", "IOA_SIZE", 85),
        ("driver_t1", "T1", 65), ("driver_t2", "T2", 65), ("driver_t3", "T3", 65),
        ("driver_k", "K", 55), ("driver_w", "W", 55), ("driver_net_address", "NET_ADDRESS", 110),
    ]),
    # ZENON-SLD.csv is the authoritative graphical equipment inventory.
    ("ZENON SLD", "#C1E3AC", [
        ("zsld_device_type", "Device Type", 95),
        ("zsld_screen_name", "Screen / Picture", 190),
        ("zsld_feeder", "Feeder / Scope", 165), ("zsld_rmu", "Equipment Name", 110), ("zsld_type", "Subtype", 85),
        ("zsld_smart", "SMART", 90),
    ]),
    # Channel IP/PORT are physical columns of ADMS-DB.csv and remain under the
    # ADMS DB group. Missing source cells stay blank; no other table fills them.
    ("ADMS DB", "#91ACDF", [
        ("adb_rmu", "RMU", 90), ("adb_gss_fid", "ADMS_GSS-FID", 160),
        ("adb_y1", "Y1", 55), ("adb_y2", "Y2", 55), ("adb_y3", "Y3", 55),
        ("adb_y4", "Y4", 55), ("adb_q1", "Q1", 55), ("adb_q2", "Q2", 55),
        ("adb_type", "Type", 80), ("adb_smart", "SMART", 90),
        ("adms_channel_ip", "IP", 120), ("adms_channel_port", "PORT", 70),
    ]),
    ("ADMS SLD", "#B6C7EA", [
        ("asld_rmu", "RMU", 90), ("asld_type", "Type", 80),
        ("asld_smart", "SMART", 90),
    ]),
    ("Analysis", "#EE94A0", [
        ("analysis_name", "NAME", 80), ("analysis_feeder", "FEEDER", 85),
        ("analysis_smart", "SMART", 85), ("analysis_type", "TYPE", 80),
        ("analysis_ip", "IP", 80),
    ]),
    ("Remarks", "#D5D8DE", [("remarks", "Remarks", 300)]),
    ("Resolution", "#D8E1EA", [("comments", "Resolution", 360)]),
]
COLUMNS = [column for _, _, columns in DATA_GROUPS for column in columns]

# Generic ZENON-SLD all-equipment inventory view used by Equipment Data Review
# whenever the user selects ALL EQUIPMENT or a non-RMU DeviceType.  RMU keeps
# the existing five-source comparison contract unchanged.
EQUIPMENT_INVENTORY_GROUPS = (
    ("Index", "#FFFFFF", [
        ("no", "No.", 55), ("rmu", "Equipment Name", 150),
    ]),
    ("ZENON SLD Inventory", "#C1E3AC", [
        ("zsld_device_type", "Device Type", 120),
        ("zsld_type", "Type", 90),
        ("zsld_smart", "SMART", 90),
        ("zsld_feeder", "Feeder / Scope", 180),
        ("zsld_screen_name", "Screen / Picture", 190),
        ("zsld_destination_name", "Destination Name", 150),
        ("zsld_display_name", "Display Name", 150),
        ("zsld_name_source", "Name Source", 150),
        ("zsld_graphic_instances", "Graphic Instances", 120),
        ("zsld_start_x", "Start X", 90),
        ("zsld_start_y", "Start Y", 90),
    ]),
)
EQUIPMENT_INVENTORY_COLUMNS = [column for _group, _color, columns in EQUIPMENT_INVENTORY_GROUPS for column in columns]

# Five-source equipment browser used for ALL/non-RMU Equipment Data Review.
# Unlike the legacy ZENON-SLD-only inventory, this view keeps ZENON SLD as the
# equipment/type anchor and shows the corresponding row from every physical
# source side-by-side.  It intentionally does not invent PASS/CLOSED workflow
# states for non-RMU classes; review rules can be promoted per equipment type
# later without another layout redesign.
EQUIPMENT_SOURCE_GROUPS = (
    ("Index", "#FFFFFF", [
        ("no", "No.", 55), ("rmu", "Equipment Name", 150),
        ("equipment_device_type", "Device Type", 115),
    ]),
    ("Source Coverage", "#EEF2F6", [
        ("equipment_source_count", "Sources", 90),
        ("equipment_missing_sources", "Missing Sources", 260),
    ]),
    ("Analysis", "#EE94A0", [
        ("analysis_name", "NAME", 80), ("analysis_feeder", "FEEDER", 85),
        ("analysis_smart", "SMART", 85), ("analysis_type", "TYPE", 80),
        ("analysis_ip", "IP", 80),
    ]),
    ("Remarks", "#D5D8DE", [("remarks", "Remarks", 300)]),
    ("Resolution", "#D8E1EA", [("comments", "Resolution / Comments", 360)]),
    ("SE", "#83D9D2", [
        ("eq_se_station", "Station", 100),
        ("eq_se_feeder", "Feeder", 150),
        ("eq_se_rmu", "Equipment Name", 130),
        ("eq_se_device_type", "Device Type", 115),
        ("eq_se_type", "Type", 100),
        ("eq_se_smart", "SMART", 90),
        ("eq_se_oh_ug", "OH / UG", 80),
        ("eq_se_ip", "IP", 120),
    ]),
    ("ZENON DB", "#E3F2D9", [
        ("eq_zdb_feeder", "Feeder", 150),
        ("eq_zdb_rmu", "Equipment Name", 130),
        ("eq_zdb_brand", "Brand", 105),
        ("eq_zdb_device_type", "Device Type", 115),
        ("eq_zdb_type", "Type", 100),
        ("eq_zdb_smart", "SMART", 90),
        ("eq_zdb_ip", "IP", 120),
        ("eq_zdb_port", "PORT", 75),
        ("eq_zdb_function_location", "Function Location", 165),
    ]),
    ("ZENON SLD", "#C1E3AC", [
        ("eq_zsld_rmu", "Equipment Name", 130),
        ("eq_zsld_device_type", "Device Type", 115),
        ("eq_zsld_feeder", "Feeder / Scope", 175),
        ("eq_zsld_type", "Type", 100),
        ("eq_zsld_screen", "Screen / Picture", 190),
        ("eq_zsld_smart", "SMART", 90),
        ("eq_zsld_ip", "IP", 120),
    ]),
    ("ADMS DB", "#91ACDF", [
        ("eq_adb_rmu", "Equipment Name", 130),
        ("eq_adb_feeder", "Feeder", 175),
        ("eq_adb_device_type", "Device Type", 115),
        ("eq_adb_type", "Type", 100),
        ("eq_adb_smart", "SMART", 90),
        ("eq_adb_ip", "IP", 120),
        ("eq_adb_port", "PORT", 75),
    ]),
    ("ADMS SLD", "#B6C7EA", [
        ("eq_asld_rmu", "Equipment Name", 130),
        ("eq_asld_feeder", "Feeder", 150),
        ("eq_asld_device_type", "Device Type", 115),
        ("eq_asld_type", "Type", 100),
        ("eq_asld_smart", "SMART", 90),
        ("eq_asld_ip", "IP", 120),
    ]),
    # ZENON-SLD extractor quality / traceability fields are intentionally not
    # customer-facing columns.  They remain available in the source adapter
    # and review-service payload for diagnostics/troubleshooting only.
)
EQUIPMENT_SOURCE_COLUMNS = [column for _group, _color, columns in EQUIPMENT_SOURCE_GROUPS for column in columns]

EDITABLE_COLUMNS = {key for key, _, _ in COLUMNS if key not in {"no", "rmu", "remarks", "comments"}}

# RMU Data Review deliberately puts the review result first so reviewers can
# see issues/reasons before scrolling through source-system fields.
_REVIEW_GROUP_NAMES = {"Index", "Analysis", "Remarks", "Resolution"}
COMPARISON_GROUPS = (
    [group for group in DATA_GROUPS if group[0] == "Analysis"]
    + [group for group in DATA_GROUPS if group[0] == "Remarks"]
    + [group for group in DATA_GROUPS if group[0] == "Resolution"]
    + [group for group in DATA_GROUPS if group[0] == "Index"]
    + [group for group in DATA_GROUPS if group[0] not in _REVIEW_GROUP_NAMES]
)
COMPARISON_COLUMNS = [column for _, _, columns in COMPARISON_GROUPS for column in columns]

# Versioned UI column-layout schema.  When new review columns are introduced,
# older saved QSettings layouts must be migrated once; otherwise a user's
# previous visible-column list silently hides the newly added fields.
COMPARISON_COLUMN_SCHEMA_VERSION = 8
COMPARISON_COLUMN_MIGRATIONS = {
    2: {"analysis_ip", "analysis_link"},
    3: {"se_smart"},
    4: {"comments"},
    5: {"adb_smart"},
    6: set(),  # v0.8.50 removes Analysis · LINK from the review schema.
    7: {"zsld_smart"},  # v0.8.130 exposes ZENON SLD SMART in RMU Data Review.
    8: {"zsld_device_type"},  # v0.8.150 makes ZENON SLD an all-equipment inventory.
}

def migrate_comparison_visible_columns(saved_columns, saved_schema_version=0):
    """Return a visible-column set migrated to the current comparison schema.

    Existing user choices are preserved.  Only columns introduced after the
    saved schema version are added automatically, and this happens once.
    """
    all_keys = {key for key, _label, _width in COMPARISON_COLUMNS}
    if not saved_columns:
        visible = set(all_keys)
    else:
        visible = set(saved_columns) & all_keys
        try:
            version = int(saved_schema_version or 0)
        except (TypeError, ValueError):
            version = 0
        for target_version in sorted(COMPARISON_COLUMN_MIGRATIONS):
            if version < target_version:
                visible |= COMPARISON_COLUMN_MIGRATIONS[target_version] & all_keys
    # Identity columns are intentionally always present in the main grid, even
    # though the frozen Row Locator duplicates them for navigation.
    visible |= {"no", "rmu"}
    return visible

# Legacy DATA geometry retained only for compatibility helpers; formal App export uses COMPARISON_GROUPS.
REPORT_MERGES = [
    "C1:G1", "H1:AB1", "AC1:AF1", "AG1:AR1",
    "AS1:AU1", "AV1:AZ1", "BA1:BA2", "BB1:BB2",
]
REPORT_GROUP_STARTS = {
    "C1": "SE", "H1": "ZENON DB", "AC1": "ZENON SLD",
    "AG1": "ADMS DB", "AS1": "ADMS SLD",
    "AV1": "Analysis", "BA1": "Remarks", "BB1": "Resolution",
}

TABULAR_SOURCE_FILTERS = [("CSV", "*.csv"), ("Excel", "*.xlsx *.xlsm")]

SOURCE_TYPES = {
    "se_list": ("SE Equipment List", TABULAR_SOURCE_FILTERS),
    "zenon_db": ("Zenon DB", TABULAR_SOURCE_FILTERS),
    "zenon_sld": ("Zenon SLD", TABULAR_SOURCE_FILTERS),
    "adms_db": ("ADMS DB", TABULAR_SOURCE_FILTERS),
    "adms_sld": ("ADMS SLD", TABULAR_SOURCE_FILTERS),
    "ioa": ("ZENON-ADMS IOA", TABULAR_SOURCE_FILTERS),
}
