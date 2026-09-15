from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    custom_review_column_key,
    equipment_review_column_key,
    equipment_review_protected_column_keys,
    equipment_source_review_groups,
    get_hidden_source_fields,
    set_hidden_source_fields,
)
from migration_report_tool.version import __version__


def test_release_version():
    assert __version__ == "0.8.172"


def test_map_fields_uses_visibility_checkboxes_not_delete_restore_buttons():
    source = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert 'QTableWidget(0, 5)' in source
    assert '["Show", "App Column", "Source Field", "Type", "Status"]' in source
    assert 'QPushButton("Show All Fields")' in source
    assert 'QPushButton("Hide Optional Fields")' in source
    assert 'QPushButton("Delete Column")' not in source
    assert 'QPushButton("Restore Optional Columns")' not in source
    assert 'self._visibility_checks' in source
    assert 'checkbox.setChecked(True if locked else field_key not in self.current_hidden_fields)' in source
    assert 'checkbox.setEnabled(not locked)' in source


def test_hidden_builtin_field_is_removed_from_equipment_review_but_mapping_definition_remains(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        key = equipment_review_column_key("adms_sld", "quality_status")
        # v0.8.172 defaults optional fields hidden. Explicitly show all first
        # so this legacy test can still verify a subsequent hide action.
        set_hidden_source_fields(store, "adms_sld", set(), "tester")
        before = {column_key for _group, _color, columns in equipment_source_review_groups(store) for column_key, _label, _width in columns}
        assert key in before
        set_hidden_source_fields(store, "adms_sld", {"quality_status"}, "tester")
        assert get_hidden_source_fields(store, "adms_sld") == {"quality_status"}
        after = {column_key for _group, _color, columns in equipment_source_review_groups(store) for column_key, _label, _width in columns}
        assert key not in after
    finally:
        store.close()


def test_hidden_user_field_is_removed_from_equipment_review_without_deleting_definition(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        store.replace_custom_source_fields(
            "adms_sld",
            [{"field_key": "new_ref", "display_name": "New Ref", "actual_column": "NewRef"}],
            "tester",
        )
        custom_key = custom_review_column_key("adms_sld", "new_ref")
        # Explicit Show All makes the source-driven USER field visible before
        # verifying that Hide removes it without deleting its mapping.
        set_hidden_source_fields(store, "adms_sld", set(), "tester")
        before = {column_key for _group, _color, columns in equipment_source_review_groups(store) for column_key, _label, _width in columns}
        assert custom_key in before

        set_hidden_source_fields(store, "adms_sld", {"new_ref"}, "tester")
        after = {column_key for _group, _color, columns in equipment_source_review_groups(store) for column_key, _label, _width in columns}
        assert custom_key not in after
        # Hide means hide only: the USER App field and its mapping still exist.
        saved = store.custom_source_fields("adms_sld")
        assert len(saved) == 1
        assert saved[0]["field_key"] == "new_ref"
        assert saved[0]["display_name"] == "New Ref"
        assert saved[0]["actual_column"] == "NewRef"
    finally:
        store.close()


def test_system_fields_cannot_be_persisted_as_hidden(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        protected_review_keys = equipment_review_protected_column_keys()
        assert equipment_review_column_key("adms_sld", "device_type") in protected_review_keys
        set_hidden_source_fields(store, "adms_sld", {"device_type", "quality_status"}, "tester")
        # schema service strips SYSTEM calculation fields from hidden preferences.
        assert get_hidden_source_fields(store, "adms_sld") == {"quality_status"}
    finally:
        store.close()
