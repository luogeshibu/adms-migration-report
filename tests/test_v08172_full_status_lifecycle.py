import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.version import __version__


class V08172FullStatusLifecycleTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_all_manual_statuses_remain_after_first_need_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "project")
            try:
                rmu = "8881B"
                store.update_rmu_review_status(rmu, "NEEDS ACTION", "alice", "Feeder mismatch")
                store.update_rmu_review_status(rmu, "UNREVIEWED", "bob", "Waiting for customer")
                store.update_rmu_review_status(rmu, "CLOSED", "carol", "Confirmed fixed")
                # This transition used to disappear because the formal case was already CLOSED.
                store.update_rmu_review_status(rmu, "UNREVIEWED", "dave", "Recheck requested")

                payload = store.rmu_full_lifecycle(rmu)
                self.assertEqual(payload["rmu_case_count"], 1)
                self.assertEqual(payload["cases"][0]["status"], "CLOSED")
                states = [
                    event["event_state"]
                    for event in payload["events"]
                    if event["entity_type"] == "RMU" and event["field_name"] == "review_status"
                ]
                self.assertEqual(states, ["NEEDS ACTION", "UNREVIEWED", "CLOSED", "UNREVIEWED"])
                self.assertEqual(payload["events"][-1]["new_value"], "UNREVIEWED")
                self.assertEqual(payload["events"][-1]["modified_by"], "dave")

                # Only a new Needs Action starts the next formal case.
                store.update_rmu_review_status(rmu, "NEEDS ACTION", "erin", "Mismatch returned")
                cases = store.issue_cases(entity_type="RMU", entity_key=rmu)
                self.assertEqual(len(cases), 2)
                self.assertEqual(cases[0]["case_no"], 2)
                self.assertEqual(cases[0]["status"], "OPEN")
                self.assertEqual(cases[1]["case_no"], 1)
                self.assertEqual(cases[1]["status"], "CLOSED")
            finally:
                store.close()

    def test_automatic_validation_reset_to_unreviewed_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "project")
            try:
                rmu = "8514B"
                row1 = {
                    "rmu": rmu,
                    "analysis_name": "TRUE", "analysis_feeder": "FALSE",
                    "analysis_smart": "TRUE", "analysis_type": "TRUE", "analysis_ip": "TRUE",
                }
                store._sync_rmu_review_analysis_hash(rmu, "hash-1", row=row1)
                store.update_rmu_review_status(rmu, "NEEDS ACTION", "alice", "Feeder mismatch")

                row2 = dict(row1)
                row2["analysis_feeder"] = "TRUE"
                store._sync_rmu_review_analysis_hash(rmu, "hash-2", row=row2)
                store.db.commit()

                payload = store.rmu_full_lifecycle(rmu)
                status_events = [
                    event for event in payload["events"]
                    if event["entity_type"] == "RMU" and event["field_name"] == "review_status"
                ]
                self.assertEqual(status_events[-1]["event_state"], "UNREVIEWED")
                self.assertEqual(status_events[-1]["old_value"], "NEEDS ACTION")
                self.assertEqual(status_events[-1]["new_value"], "UNREVIEWED")
                self.assertEqual(status_events[-1]["modified_by"], "SYSTEM")
            finally:
                store.close()

    def test_compact_tracker_uses_equipment_scoped_case_label(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        self.assertIn('"Time", "Equipment Case", "Status", "Issue", "Comments", "User"', ui)
        self.assertIn('f"{display_name}-{case_no:03d}" if case_no else "—"', ui)


if __name__ == "__main__":
    unittest.main()
