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
    ("ZENON DB", "#E3F2D9", [
        ("zdb_feeder", "Feeder", 115), ("zdb_rmu", "RMU", 90), ("zdb_brand", "Brand", 100),
        ("zdb_device", "Device", 90), ("zdb_nop", "NOP", 65), ("zdb_smart", "SMART", 70),
        ("zdb_vip", "VIP", 80), ("zdb_function_location", "Function Location", 150),
    ]),
    ("Driver Info", "#E3F2D9", [
        ("driver_ip", "IP", 120), ("driver_port", "PORT", 70), ("driver_link_address", "LINK_ADDRESS", 110),
        ("driver_link_address_size", "LINK_ADDRESS_SIZE", 130), ("driver_cot_size", "COT_SIZE", 85),
        ("driver_coa_size", "COA_SIZE", 85), ("driver_ioa_size", "IOA_SIZE", 85),
        ("driver_t1", "T1", 65), ("driver_t2", "T2", 65), ("driver_t3", "T3", 65),
        ("driver_k", "K", 55), ("driver_w", "W", 55), ("driver_net_address", "NET_ADDRESS", 110),
    ]),
    ("ZENON SLD XML", "#C1E3AC", [
        ("zsld_screen_name", "Screen Name", 190),
        ("zsld_feeder", "Feeder", 155), ("zsld_rmu", "RMU", 90), ("zsld_type", "Type", 80),
    ]),
    ("ADMS DB", "#91ACDF", [
        ("adb_rmu", "RMU", 90), ("adb_gss_fid", "ADMS_GSS-FID", 160),
        ("adb_y1", "Y1", 55), ("adb_y2", "Y2", 55), ("adb_y3", "Y3", 55),
        ("adb_y4", "Y4", 55), ("adb_q1", "Q1", 55), ("adb_q2", "Q2", 55),
        ("adb_type", "Type", 80),
    ]),
    ("ADMS Channel", "#91ACDF", [
        ("adms_channel_ip", "IP", 120), ("adms_channel_port", "PORT", 70),
    ]),
    ("ADMS SLD", "#B6C7EA", [
        ("asld_rmu", "RMU", 90), ("asld_type", "Type", 80),
        ("asld_smart", "SMART", 90), ("asld_link", "LINK", 100),
    ]),
    ("Analysis", "#EE94A0", [
        ("analysis_name", "NAME", 80), ("analysis_feeder", "FEEDER", 85),
        ("analysis_smart", "SMART", 85), ("analysis_type", "TYPE", 80),
        ("analysis_ip", "IP", 80), ("analysis_link", "LINK", 80),
    ]),
    ("Remarks", "#D5D8DE", [("remarks", "Remarks", 300)]),
    ("Comments", "#D8E1EA", [("comments", "Comments", 360)]),
]
COLUMNS = [column for _, _, columns in DATA_GROUPS for column in columns]
EDITABLE_COLUMNS = {key for key, _, _ in COLUMNS if key not in {"no", "rmu"}}

# RMU Data Review deliberately puts the review result first so reviewers can
# see issues/reasons before scrolling through source-system fields.
_REVIEW_GROUP_NAMES = {"Index", "Analysis", "Remarks", "Comments"}
COMPARISON_GROUPS = (
    [group for group in DATA_GROUPS if group[0] == "Analysis"]
    + [group for group in DATA_GROUPS if group[0] == "Remarks"]
    + [group for group in DATA_GROUPS if group[0] == "Comments"]
    + [group for group in DATA_GROUPS if group[0] == "Index"]
    + [group for group in DATA_GROUPS if group[0] not in _REVIEW_GROUP_NAMES]
)
COMPARISON_COLUMNS = [column for _, _, columns in COMPARISON_GROUPS for column in columns]

# Versioned UI column-layout schema.  When new review columns are introduced,
# older saved QSettings layouts must be migrated once; otherwise a user's
# previous visible-column list silently hides the newly added fields.
COMPARISON_COLUMN_SCHEMA_VERSION = 3
COMPARISON_COLUMN_MIGRATIONS = {
    2: {"analysis_ip", "analysis_link"},
    3: {"se_smart"},
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
    "C1:G1", "H1:O1", "P1:AB1", "AC1:AF1", "AG1:AO1",
    "AP1:AR1", "AS1:AV1", "AW1:AZ1", "BA1:BA2", "BB1:BB2",
]
REPORT_GROUP_STARTS = {
    "C1": "SE", "H1": "ZENON DB", "P1": "Driver Info", "AC1": "ZENON SLD XML",
    "AG1": "ADMS DB", "AP1": "ADMS Channel", "AS1": "ADMS SLD",
    "AW1": "Analysis", "BA1": "Remarks", "BB1": "Comments",
}

SOURCE_TYPES = {
    "se_list": ("SE Equipment List", [("Excel", "*.xlsx")]),
    "zenon_xml": ("Zenon XML", [("XML", "*.xml")]),
    "zenon_db": ("Zenon DB", [("CSV", "*.csv")]),
    "zenon_sld": ("Zenon SLD CSV (optional)", [("CSV", "*.csv")]),
    "adms_db": ("ADMS DB", [("CSV", "*.csv")]),
    "adms_sld": ("ADMS SLD", [("CSV", "*.csv")]),
    "ioa": ("ZENON-ADMS IOA", [("CSV", "*.csv")]),
}
