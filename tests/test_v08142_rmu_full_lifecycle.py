import tempfile
import unittest
from pathlib import Path

from migration_report_tool.storage import ProjectStore
from migration_report_tool.version import __version__


class RMUFullLifecycleTests(unittest.TestCase):
    def test_release_and_schema_remain_compatible(self):
        self.assertEqual(__version__, "0.8.215")
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                self.assertEqual(store.project_schema_version(), 12)
            finally:
                store.close()

    def test_rmu_full_lifecycle_combines_rmu_and_child_signal_cases_only(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            signal_meta = {
                "signal_category": "STATUS_CMD",
                "point_no": "13024",
                "signal_name": "16934 Y2 i_b_value(A)",
                "signal_snapshot_json": "{}",
            }
            other_meta = {
                "signal_category": "ANALOG",
                "point_no": "9999",
                "signal_name": "Other RMU signal",
                "signal_snapshot_json": "{}",
            }
            try:
                # RMU case 1: open -> comment -> close.
                store.update_rmu_review_status("15953", "NEEDS ACTION", "alice", "FEEDER mismatch")
                store.update_rmu_manual_review_comment("15953", "Confirm feeder with site", "bob")
                store.update_rmu_review_status("15953", "CLOSED", "carol", "Feeder corrected")

                # RMU case 2: a real reopen cycle must remain a separate case.
                store.update_rmu_review_status("15953", "NEEDS ACTION", "dave", "Mismatch returned")

                # A child signal case belongs in the same RMU-centric lifecycle.
                store.update_db_smart_review(
                    "sig-15953-1", "15953", "comments", "MODIFY | Verify signal mapping", "erin",
                    site_name="1-ABH", metadata=signal_meta,
                )
                store.update_db_smart_review(
                    "sig-15953-1", "15953", "review_status", "NEEDS ACTION", "erin",
                    site_name="1-ABH", metadata=signal_meta,
                )
                store.update_db_smart_review(
                    "sig-15953-1", "15953", "review_status", "CLOSED", "frank",
                    site_name="1-ABH", metadata=signal_meta,
                )

                # A different RMU must never leak into 15953's timeline.
                store.update_db_smart_review(
                    "sig-other", "10689", "review_status", "NEEDS ACTION", "mallory",
                    site_name="1-ABH", metadata=other_meta,
                )

                lifecycle = store.rmu_full_lifecycle("15953")
                self.assertEqual(lifecycle["rmu"], "15953")
                self.assertEqual(lifecycle["case_count"], 3)
                self.assertEqual(lifecycle["rmu_case_count"], 2)
                self.assertEqual(lifecycle["signal_case_count"], 1)
                self.assertEqual(lifecycle["open_count"], 1)
                self.assertEqual(lifecycle["closed_count"], 2)
                self.assertGreaterEqual(lifecycle["event_count"], 7)
                self.assertGreaterEqual(lifecycle["participant_count"], 6)
                self.assertTrue(lifecycle["first_activity_at"])
                self.assertTrue(lifecycle["last_activity_at"])

                scopes = {event["entity_type"] for event in lifecycle["events"]}
                self.assertEqual(scopes, {"RMU", "SIGNAL"})
                self.assertTrue(all(event["rmu"] == "15953" for event in lifecycle["events"]))
                self.assertTrue(any(event["point_no"] == "13024" for event in lifecycle["events"]))
                self.assertFalse(any(event["modified_by"] == "mallory" for event in lifecycle["events"]))

                # Events are returned in deterministic chronological order for UI display.
                ordering = [
                    (event.get("modified_at") or "", int(event.get("id") or 0))
                    for event in lifecycle["events"]
                ]
                self.assertEqual(ordering, sorted(ordering))
            finally:
                store.close()

    def test_empty_rmu_lifecycle_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                lifecycle = store.rmu_full_lifecycle("17230")
                self.assertEqual(lifecycle["case_count"], 0)
                self.assertEqual(lifecycle["events"], [])
                self.assertEqual(lifecycle["open_count"], 0)
            finally:
                store.close()

    def test_rmu_review_ui_contains_in_page_lifecycle_panel(self):
        source = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        self.assertIn('self.comparison_lifecycle_title = QLabel("Equipment Action Tracking")', source)
        self.assertIn("self.comparison_page_splitter = QSplitter(Qt.Vertical)", source)
        self.assertIn("self.store.rmu_full_lifecycle(rmu)", source)
        self.assertIn('QPushButton("Open Full Lifecycle")', source)
        self.assertIn('menu.addAction(ui_tr("View Full Equipment Lifecycle...", self.ui_language), self._open_selected_rmu_lifecycle)', source)
        self.assertIn("RMUFullLifecycleDialog(", source)


if __name__ == "__main__":
    unittest.main()
