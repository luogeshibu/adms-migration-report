from __future__ import annotations

from pathlib import Path


def test_hidden_column_preferences_persist_and_reset(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", str(tmp_path / "user-data"))

    from migration_report_tool.infrastructure.database.global_settings_store import (
        review_hidden_columns,
        replace_review_hidden_columns,
    )

    assert review_hidden_columns("rmu_data_review") is None

    replace_review_hidden_columns({"adb_smart", "custom__adms_sld__new_link"})
    assert review_hidden_columns("rmu_data_review") == {
        "adb_smart",
        "custom__adms_sld__new_link",
    }

    # Reset Columns persists an empty explicit-hidden set.  A future/new column
    # is therefore visible automatically because it is not hidden.
    replace_review_hidden_columns(set())
    assert review_hidden_columns("rmu_data_review") == set()


def test_new_columns_are_visible_with_explicit_hidden_model(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", str(tmp_path / "user-data"))

    from migration_report_tool.infrastructure.database.global_settings_store import (
        review_hidden_columns,
        replace_review_hidden_columns,
    )

    replace_review_hidden_columns({"remarks"})
    hidden = review_hidden_columns("rmu_data_review") or set()

    old_columns = {"no", "rmu", "remarks", "adb_rmu"}
    new_columns = old_columns | {"custom__adms_sld__abc"}
    visible = (new_columns - hidden) | {"no", "rmu"}

    assert "remarks" not in visible
    assert "custom__adms_sld__abc" in visible
