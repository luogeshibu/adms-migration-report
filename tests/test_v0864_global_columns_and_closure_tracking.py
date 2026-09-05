from __future__ import annotations

import os
from pathlib import Path
import tempfile

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.services.schema_service import custom_review_column_key, rmu_review_groups
from migration_report_tool.infrastructure.database.migrations import TARGET_SCHEMA_VERSION


def test_user_app_column_and_source_field_mapping_are_global():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(root / "user-data")
        try:
            a = ProjectStore(root / "site-a")
            b = ProjectStore(root / "site-b")
            try:
                a.replace_custom_source_fields(
                    "adms_sld",
                    [{"field_key": "acb", "display_name": "ACB", "actual_column": "NEW ID"}],
                    "tester",
                )
                a_fields = a.custom_source_fields("adms_sld")
                b_fields = b.custom_source_fields("adms_sld")
                assert [(x["field_key"], x["display_name"], x["actual_column"]) for x in a_fields] == [("acb", "ACB", "NEW ID")]
                assert [(x["field_key"], x["display_name"], x["actual_column"]) for x in b_fields] == [("acb", "ACB", "NEW ID")]

                # The global mapping exists in site B. If its physical file does
                # not contain that globally selected header, values remain blank.
                source = root / "ADMS-SLD-B.csv"
                source.write_text("RMU,TYPE,SMART\n1001,2L1T,SMART\n", encoding="utf-8")
                b.set_source("adms_sld", source)
                rows, _ = build_comparison(b)
                key = custom_review_column_key("adms_sld", "acb")
                assert rows and rows[0].get(key, "") == ""
                adms_group = next(cols for group, _color, cols in rmu_review_groups(b) if group == "ADMS SLD")
                assert (key, "ACB", 130) in adms_group

                # Changing the Source Field at site B updates the same global
                # mapping immediately for site A as well.
                b.replace_custom_source_fields(
                    "adms_sld",
                    [{"field_key": "acb", "display_name": "ACB", "actual_column": "TYPE"}],
                    "tester-b",
                )
                assert a.custom_source_fields("adms_sld")[0]["actual_column"] == "TYPE"
                assert b.custom_source_fields("adms_sld")[0]["actual_column"] == "TYPE"

                # Deleting the USER App column is global; stale local bindings
                # no longer make the live column reappear.
                b.replace_custom_source_fields("adms_sld", [], "tester-b")
                assert a.custom_source_fields("adms_sld") == []
                assert b.custom_source_fields("adms_sld") == []
            finally:
                a.close(); b.close()
        finally:
            if old is None:
                os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
            else:
                os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = old


def test_needs_action_rmu_remains_tracked_until_explicit_close_and_can_reopen():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            store.update_rmu_review_status("17233", "NEEDS ACTION", "reviewer")
            counts = store.rmu_action_tracking_counts()
            assert counts == {"OPEN": 1, "CLOSED": 0, "TOTAL": 1}
            record = store.rmu_action_tracking()[0]
            assert record["rmu"] == "17233"
            assert record["tracking_status"] == "OPEN"
            assert int(record["open_count"]) == 1

            # An Unreviewed/reset state cannot silently drop the follow-up item.
            store.update_rmu_review_status("17233", "UNREVIEWED", "reviewer")
            assert store.rmu_action_tracking_counts()["OPEN"] == 1

            store.update_rmu_review_status("17233", "CLOSED", "reviewer")
            counts = store.rmu_action_tracking_counts()
            assert counts == {"OPEN": 0, "CLOSED": 1, "TOTAL": 1}
            assert store.rmu_action_tracking()[0]["closed_at"]

            store.update_rmu_review_status("17233", "NEEDS ACTION", "reviewer")
            record = store.rmu_action_tracking()[0]
            assert record["tracking_status"] == "OPEN"
            assert int(record["open_count"]) == 2
        finally:
            store.close()


def test_schema_v7_contains_rmu_action_tracking():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            assert store.project_schema_version() == TARGET_SCHEMA_VERSION
            names = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert "rmu_action_tracking" in names
        finally:
            store.close()


def test_source_file_selection_is_integrated_into_each_app_table_row():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "choose_source_file_for_table" in ui
    assert 'table.setCellWidget(row, 1, source_button)' in ui
    # The two old ambiguous footer actions are no longer constructed.
    assert 'active_file_btn = QPushButton("Choose Active File...")' not in ui
    assert 'add_files_btn = QPushButton("Import Source File...")' not in ui
