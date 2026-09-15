from pathlib import Path

from openpyxl import Workbook

from migration_report_tool.config.sources import schema_for
from migration_report_tool.infrastructure.parsers import (
    read_mapped_rows,
    resolve_source_excel_sheet_name,
    validate_source_file,
)


ADMS_SLD_MAIN_HEADERS = [
    "GFile", "facID", "facName", "DeviceType", "DeviceName", "IsSmart",
    "SmartType", "SmartSource", "DeviceForm", "ParentRMU", "RMUType",
    "DeviceSubtype", "ProfileDeviceType", "XML Element", "ElementID", "keyid",
    "key_name", "p_NameString", "StandardFile", "StandardDevref", "ActualDevref",
    "SymbolValidation", "ValidationIssue", "NameSource", "NameConfidence",
    "DisplayLabel", "DisplayLabelDistance", "QualityStatus", "x", "y", "w", "h",
]


def _make_adms_sld_book(path: Path) -> None:
    wb = Workbook()
    overview = wb.active
    overview.title = "解析概览"
    overview.append(["项目", "值"])
    overview.append(["说明", "这不是设备数据表"])

    ws = wb.create_sheet("ADMS-SLD主设备")
    ws.append(ADMS_SLD_MAIN_HEADERS)
    ws.append([
        "JED-STH-ADEL.sln.pic.g", "379991", "AH303", "RMU", "32954", "YES",
        "SMART", "Profile/Context", "COMPOSITE", "", "3L1T", "3L1T", "RMU",
        "组合识别", "2000046", "", "", "", "组合设备（内部图元逐项校验）", "", "",
        "COMPOSITE", "", "identify_rmus()", "HIGH", "32954", 0, "PASS",
        2789, 467, 220, 220,
    ])
    wb.save(path)


def test_adms_sld_auto_prefers_main_equipment_sheet(tmp_path):
    path = tmp_path / "ADMS-SLD.xlsx"
    _make_adms_sld_book(path)

    assert schema_for("adms_sld").sheet_name == "ADMS-SLD主设备"
    assert resolve_source_excel_sheet_name("adms_sld", path) == "ADMS-SLD主设备"

    mapped = read_mapped_rows("adms_sld", path, strict=True)
    assert len(mapped.rows) == 1
    row = mapped.rows[0]
    assert row["rmu"] == "32954"
    assert row["device_type"] == "RMU"
    assert row["rmu_type"] == "3L1T"
    assert row["smart"] == "SMART"
    assert row["feeder"] == "AH303"


def test_adms_sld_main_sheet_maps_every_physical_header(tmp_path):
    path = tmp_path / "ADMS-SLD.xlsx"
    _make_adms_sld_book(path)
    validation = validate_source_file("adms_sld", path)

    assert validation.errors == ()
    assert validation.ignored_columns == ()
    expected = {
        "rmu": "DeviceName",
        "device_type": "DeviceType",
        "rmu_type": "RMUType",
        "smart": "SmartType",
        "feeder": "facName",
        "g_file": "GFile",
        "fac_id": "facID",
        "is_smart": "IsSmart",
        "smart_source": "SmartSource",
        "device_form": "DeviceForm",
        "parent_rmu": "ParentRMU",
        "device_subtype": "DeviceSubtype",
        "profile_device_type": "ProfileDeviceType",
        "xml_element": "XML Element",
        "element_id": "ElementID",
        "key_id": "keyid",
        "key_name": "key_name",
        "p_name_string": "p_NameString",
        "standard_file": "StandardFile",
        "standard_devref": "StandardDevref",
        "actual_devref": "ActualDevref",
        "symbol_validation": "SymbolValidation",
        "validation_issue": "ValidationIssue",
        "name_source": "NameSource",
        "name_confidence": "NameConfidence",
        "display_label": "DisplayLabel",
        "display_label_distance": "DisplayLabelDistance",
        "quality_status": "QualityStatus",
        "x": "x", "y": "y", "w": "w", "h": "h",
    }
    for app_key, source_header in expected.items():
        assert validation.mapping_by_key[app_key].actual_column == source_header


def test_manual_sheet_selection_still_overrides_source_default(tmp_path):
    path = tmp_path / "ADMS-SLD.xlsx"
    _make_adms_sld_book(path)
    assert resolve_source_excel_sheet_name("adms_sld", path, "解析概览") == "解析概览"
