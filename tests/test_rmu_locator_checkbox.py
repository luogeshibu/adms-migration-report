from pathlib import Path
import tempfile

from migration_report_tool.storage import ProjectStore


def test_rmu_locator_checked_checkbox_is_persistent_business_state():
    source = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "SpreadsheetTableWidget(0, 5)" in source
    assert '("locator_rmu", "RMU", 90)' in source
    assert '("locator_checked", "Checked", 74)' in source
    assert 'setHorizontalHeaderLabels(["No.", "RMU", "Checked", "Analysis", "Review"])' in source
    assert "self.comparison_locator.setCellWidget(r, 2, select_host)" in source
    assert "_on_comparison_locator_check_passed_toggled" in source
    assert "update_rmu_check_passed" in source
    assert "_sync_comparison_checkboxes_from_rows" not in source


def test_checked_flag_survives_reopen_and_is_audited():
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td) / "1-ABH"
        store = ProjectStore(folder)
        try:
            store.update_rmu_check_passed("10689", True, "reviewer-a")
            record = store.rmu_review_map()["10689"]
            assert int(record["check_passed"]) == 1
            assert record["check_passed_by"] == "reviewer-a"
            assert record["check_passed_at"]
            audit = next(item for item in store.changes() if item["field_name"] == "rmu_check_passed")
            assert audit["new_value"] == "PASS"
        finally:
            store.close()

        reopened = ProjectStore(folder)
        try:
            record = reopened.rmu_review_map()["10689"]
            assert int(record["check_passed"]) == 1
            reopened.update_rmu_check_passed("10689", False, "reviewer-b")
            record = reopened.rmu_review_map()["10689"]
            assert int(record["check_passed"]) == 0
            assert record["check_passed_by"] == ""
            assert record["check_passed_at"] == ""
        finally:
            reopened.close()
