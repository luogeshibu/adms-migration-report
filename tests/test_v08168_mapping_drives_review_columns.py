from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    custom_review_column_key,
    equipment_source_review_groups,
    get_hidden_source_fields,
    set_hidden_source_fields,
)
from migration_report_tool.version import __version__


def _group_columns(groups, group_name):
    for name, _color, columns in groups:
        if name == group_name:
            return list(columns)
    raise AssertionError(f"missing group: {group_name}")


def test_release_version():
    assert __version__ == "0.8.172"


def test_equipment_review_se_group_mirrors_live_physical_header(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        source = tmp_path / "SE.csv"
        source.write_text(
            "SS,FEEDER,EQUIPMENT,EQUIP. TYPE,OH / UG\n"
            "ADEL,ADEL-03,1917,SMART,UG\n",
            encoding="utf-8",
        )
        store.set_source("se_list", source)

        se_columns = _group_columns(equipment_source_review_groups(store), "SE")
        assert [label for _key, label, _width in se_columns] == [
            "SS", "FEEDER", "EQUIPMENT", "EQUIP. TYPE", "OH / UG"
        ]
        keys = {key for key, _label, _width in se_columns}
        # No phantom SYSTEM rows when the physical file does not have them.
        assert "eq_se_device_type" not in keys
        assert "eq_se_type" not in keys
        assert "eq_se_ip" not in keys
    finally:
        store.close()


def test_map_fields_hide_show_is_review_source_of_truth_and_system_stays_visible(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        source = tmp_path / "SE.csv"
        source.write_text(
            "SS,FEEDER,EQUIPMENT,EQUIP. TYPE,OH / UG\n"
            "ADEL,ADEL-03,1917,SMART,UG\n",
            encoding="utf-8",
        )
        store.set_source("se_list", source)

        # station + feeder requested hidden: feeder is SYSTEM and must be stripped.
        set_hidden_source_fields(store, "se_list", {"station", "feeder"}, "tester")
        assert get_hidden_source_fields(store, "se_list") == {"station"}
        se_columns = _group_columns(equipment_source_review_groups(store), "SE")
        labels = [label for _key, label, _width in se_columns]
        assert "SS" not in labels
        assert "FEEDER" in labels
    finally:
        store.close()


def test_new_saved_physical_column_appears_as_same_named_app_review_column(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        source = tmp_path / "SE.csv"
        source.write_text(
            "SS,FEEDER,EQUIPMENT,EQUIP. TYPE,OH / UG\n"
            "ADEL,ADEL-03,1917,SMART,UG\n",
            encoding="utf-8",
        )
        copied = store.set_source("se_list", source)
        # Simulate v0.8.167 Map Fields discovering/saving a brand-new header.
        copied.write_text(
            "SS,FEEDER,EQUIPMENT,EQUIP. TYPE,OH / UG,NEW COLUMN\n"
            "ADEL,ADEL-03,1917,SMART,UG,VALUE\n",
            encoding="utf-8",
        )
        store.replace_custom_source_fields(
            "se_list",
            [{"field_key": "source_new_column", "display_name": "NEW COLUMN", "actual_column": "NEW COLUMN"}],
            "tester",
        )

        se_columns = _group_columns(equipment_source_review_groups(store), "SE")
        assert (custom_review_column_key("se_list", "source_new_column"), "NEW COLUMN", 130) in se_columns
    finally:
        store.close()


def test_columns_dialog_no_longer_competes_with_map_fields_for_source_visibility():
    source = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "physical source-field visibility is controlled only in Map" in source
    assert "dialog_groups = tuple(group for group in all_groups if group[0] not in source_group_names)" in source
    assert "stale_source_hides = self.comparison_hidden_keys & source_review_keys" in source
    assert "self._configure_comparison_headers()" in source
