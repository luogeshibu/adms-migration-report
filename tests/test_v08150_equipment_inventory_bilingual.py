from pathlib import Path

from migration_report_tool.config.source_modules import MODULE_BY_KEY
from migration_report_tool.infrastructure.parsers import read_mapped_rows, validate_source_file
from migration_report_tool.services.rmu_review_service import _filter_zenon_inventory_for_profile
from migration_report_tool.services.schema_service import system_logic_field_keys
from migration_report_tool.version import __version__


INVENTORY_HEADERS = [
    "ScriptVersion", "XMLFile", "Picture", "DeviceType", "SubType", "SMART", "DeviceName",
    "DestinationName", "DisplayName", "DeviceScope", "ResolvedFullName", "FullDestination",
    "RawSubstituteDestination", "LinkName", "SubstituteSource", "Vendor", "NameSource",
    "NameStatus", "Confidence", "VariableRootMatch", "ClassificationReason", "Element",
    "ElementName", "StartX", "StartY", "GraphicInstances", "Warning",
]


def _inventory_csv(path: Path):
    path.write_text(
        ",".join(INVENTORY_HEADERS) + "\n" +
        "4.4,SITE.XML,FEEDER-01,RMU,2L1T,SMART,1001,1001,1001,REG-AREA-FEEDER-1,"
        "REG-AREA-FEEDER-1-1001,REG-AREA-FEEDER-1-1001,REG-AREA-FEEDER-1-1001,RMU_LINK,ORMU*,VendorX,"
        "Destination+DisplayText,OK,HIGH,YES,explicit RMU symbol,Elements_1,RMU_1,100,200,1,\n" +
        "4.4,SITE.XML,FEEDER-01,CB,CB,,W01,W01,,REG_13,REG_13_W01,REG_13_W01,RAW,CB_LINK,ICCP*,,"
        "SubstituteDestination,OK,HIGH,NO,explicit breaker symbol,Elements_2,CB_1,10,20,1,\n",
        encoding="utf-8",
    )


def test_release_version():
    assert __version__ == "0.8.150"


def test_device_inventory_contract_auto_maps_every_physical_header(tmp_path):
    source = tmp_path / "ZENON-SLD.csv"
    _inventory_csv(source)
    result = validate_source_file("zenon_sld", source, {})
    assert not result.errors
    assert not result.warnings
    assert result.ignored_columns == ()
    expected = {
        "device_type": "DeviceType",
        "rmu": "DeviceName",
        "feeder": "DeviceScope",
        "cabinet_type": "SubType",
        "screen_name": "Picture",
        "smart": "SMART",
        "duplicate_count": "GraphicInstances",
        "warning": "Warning",
        "script_version": "ScriptVersion",
        "xml_file": "XMLFile",
        "destination_name": "DestinationName",
        "display_name": "DisplayName",
        "resolved_full_name": "ResolvedFullName",
        "full_destination": "FullDestination",
        "raw_substitute_destination": "RawSubstituteDestination",
        "link_name": "LinkName",
        "substitute_source": "SubstituteSource",
        "vendor": "Vendor",
        "name_source": "NameSource",
        "name_status": "NameStatus",
        "confidence": "Confidence",
        "variable_root_match": "VariableRootMatch",
        "classification_reason": "ClassificationReason",
        "element": "Element",
        "element_name": "ElementName",
        "start_x": "StartX",
        "start_y": "StartY",
    }
    for key, physical in expected.items():
        assert result.mapping_by_key[key].actual_column == physical


def test_current_equipment_review_profile_filters_all_equipment_inventory_to_rmu(tmp_path):
    source = tmp_path / "ZENON-SLD.csv"
    _inventory_csv(source)
    mapped = read_mapped_rows("zenon_sld", source, {}).rows
    assert {row["device_type"] for row in mapped} == {"RMU", "CB"}
    rmu_rows = _filter_zenon_inventory_for_profile(mapped, "RMU")
    assert len(rmu_rows) == 1
    assert rmu_rows[0]["rmu"] == "1001"
    assert rmu_rows[0]["feeder"] == "REG-AREA-FEEDER-1"
    assert rmu_rows[0]["cabinet_type"] == "2L1T"


def test_legacy_rmu_only_zenon_sld_still_loads(tmp_path):
    source = tmp_path / "legacy.csv"
    source.write_text(
        "RMU,Feeder,CabinetType,Screen name,SMART,DuplicateCount,Warning\n"
        "1001,F-01,2L1T,PIC-1,SMART,1,\n",
        encoding="utf-8",
    )
    result = validate_source_file("zenon_sld", source, {})
    assert not result.errors
    mapped = read_mapped_rows("zenon_sld", source, {}).rows
    assert _filter_zenon_inventory_for_profile(mapped, "RMU") == list(mapped)


def test_device_type_is_protected_system_mapping_and_module_is_equipment_named():
    assert "device_type" in system_logic_field_keys("zenon_sld")
    module = MODULE_BY_KEY["rmu_review"]
    assert module.label == "Equipment Data Review"
    zsld = next(item for item in module.tables if item.source_type == "zenon_sld")
    for key in ("device_type", "rmu", "feeder", "cabinet_type", "screen_name", "name_status", "confidence"):
        assert key in zsld.field_keys


def test_bilingual_runtime_contract_and_equipment_ui_name():
    i18n = Path("src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
    assert 'LANG_ZH_CN = "zh_CN"' in i18n
    assert '"Equipment Data Review": "设备数据审核"' in i18n
    assert '("Map Fields · ", "字段映射 · ")' in i18n
    assert 'Technical field names and source headers remain unchanged' in i18n

    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert '("Equipment Data Review", 2, "rmu")' in ui
    assert 'self.settings.value("ui/language", LANG_EN)' in ui
    assert 'form.addRow("Interface Language", language_widget)' in ui
    assert 'self.equipment_profile_combo.addItem("RMU (Active)", "RMU")' in ui
