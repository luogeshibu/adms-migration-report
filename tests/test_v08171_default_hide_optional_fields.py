from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    get_hidden_source_fields,
    set_hidden_source_fields,
    system_logic_field_keys,
)
from migration_report_tool.config.sources import schema_for
from migration_report_tool.version import __version__


def test_release_version():
    assert __version__ == "0.8.172"


def test_optional_source_fields_are_hidden_by_default(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        schema = schema_for("adms_sld")
        locked = system_logic_field_keys("adms_sld")
        hidden = get_hidden_source_fields(store, "adms_sld")
        assert hidden
        assert all(spec.key in hidden for spec in schema.fields if spec.key not in locked)
        assert not (hidden & locked)
    finally:
        store.close()


def test_source_driven_custom_fields_are_hidden_by_default(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        store.replace_custom_source_fields(
            "adms_sld",
            [{"field_key": "new_ref", "display_name": "New Ref", "actual_column": "NewRef"}],
            "tester",
        )
        assert "new_ref" in get_hidden_source_fields(store, "adms_sld")
    finally:
        store.close()


def test_explicit_show_all_is_respected(tmp_path):
    store = ProjectStore(tmp_path / "project")
    try:
        # Saving an empty hidden set means the reviewer deliberately chose
        # Show All Fields; defaults must not be re-applied on the next open.
        set_hidden_source_fields(store, "adms_sld", set(), "tester")
        assert "adms_sld" in (store.config.get("hidden_source_fields", {}) or {})
        assert get_hidden_source_fields(store, "adms_sld") == set()
    finally:
        store.close()
