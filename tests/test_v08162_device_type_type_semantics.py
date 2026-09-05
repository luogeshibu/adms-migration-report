from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.config.sources import schema_for
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.rmu_review_service import build_equipment_source_view
from migration_report_tool.services.schema_service import (
    equipment_review_column_key,
    equipment_review_protected_column_keys,
    equipment_source_review_groups,
)
from migration_report_tool.version import __version__


class MultiAdapter(SourceAdapter):
    def __init__(self, tables):
        self.tables = {key: list(value) for key, value in tables.items()}

    def load_rows(self, source_type: str):
        return [dict(row) for row in self.tables.get(source_type, [])]


def _field(source_type: str, key: str):
    schema = schema_for(source_type)
    assert schema is not None
    return next(item for item in schema.fields if item.key == key)


def test_release_version():
    assert __version__ == "0.8.162"


def test_device_type_and_type_are_separate_source_contracts():
    for source_type in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"):
        device_type = _field(source_type, "device_type")
        assert "TYPE" not in {alias.upper() for alias in device_type.aliases}

    # Existing subtype semantics remain intact.
    assert "TYPE" in {alias.upper() for alias in _field("se_list", "rmu_type").aliases}
    assert "DEVICE" in {alias.upper() for alias in _field("zenon_db", "rmu_type").aliases}
    assert "TYPE" in {alias.upper() for alias in _field("adms_db", "rmu_type").aliases}
    assert "TYPE" in {alias.upper() for alias in _field("adms_sld", "rmu_type").aliases}


def test_all_five_source_groups_expose_device_type_and_type(tmp_path: Path):
    store = ProjectStore(tmp_path / "project")
    try:
        groups = equipment_source_review_groups(store)
        by_group = {group: {key for key, _label, _width in columns} for group, _color, columns in groups}
        expected = {
            "SE": ("eq_se_device_type", "eq_se_type"),
            "ZENON DB": ("eq_zdb_device_type", "eq_zdb_type"),
            "ZENON SLD": ("eq_zsld_device_type", "eq_zsld_type"),
            "ADMS DB": ("eq_adb_device_type", "eq_adb_type"),
            "ADMS SLD": ("eq_asld_device_type", "eq_asld_type"),
        }
        for group, keys in expected.items():
            assert set(keys).issubset(by_group[group])
    finally:
        store.close()


def test_source_device_type_stays_source_faithful_and_type_keeps_subtype(tmp_path: Path):
    store = ProjectStore(tmp_path / "project")
    try:
        rows, _ = build_equipment_source_view(
            store,
            "RMU",
            MultiAdapter({
                "zenon_sld": [{
                    "device_type": "RMU", "rmu": "22959", "feeder": "ADEL-27",
                    "cabinet_type": "3L1T", "smart": "NORMAL",
                }],
                # Current SE export may not have a Device Type physical column.
                # It must remain blank rather than being copied from ZENON SLD.
                "se_list": [{
                    "rmu": "22959", "feeder": "ADEL-27", "rmu_type": "3L1T",
                    "smart": "NORMAL", "oh_ug": "UG",
                }],
                "zenon_db": [{
                    "rmu": "22959", "feeder": "ADEL-27", "device_type": "RMU",
                    "rmu_type": "3L1T", "smart": "NORMAL",
                }],
                "adms_db": [{
                    "rmu": "22959", "gss_fid": "ADEL-27", "device_type": "RMU",
                    "rmu_type": "3L1T", "smart": "NORMAL",
                }],
                "adms_sld": [{
                    "rmu": "22959", "feeder": "ADEL-27", "device_type": "RMU",
                    "rmu_type": "3L1T", "smart": "NORMAL",
                }],
            }),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["equipment_device_type"] == "RMU"
        assert row["eq_se_device_type"] == ""
        assert row["eq_se_type"] == "3L1T"
        assert row["eq_zdb_device_type"] == "RMU"
        assert row["eq_zdb_type"] == "3L1T"
        assert row["eq_adb_device_type"] == "RMU"
        assert row["eq_adb_type"] == "3L1T"
        assert row["eq_asld_device_type"] == "RMU"
        assert row["eq_asld_type"] == "3L1T"
    finally:
        store.close()


def test_source_device_type_columns_are_system_protected():
    protected = equipment_review_protected_column_keys()
    for source_type in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"):
        assert equipment_review_column_key(source_type, "device_type") in protected
