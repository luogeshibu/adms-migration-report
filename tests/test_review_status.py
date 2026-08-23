import unittest
import tempfile
from pathlib import Path

from migration_report_tool.storage import ProjectStore

from migration_report_tool.review_status import analysis_review_state, field_false_color


def row(**updates):
    value = {
        "analysis_name": "TRUE",
        "analysis_feeder": "TRUE",
        "analysis_smart": "TRUE",
        "analysis_type": "TRUE",
        "analysis_ip": "TRUE",
        "analysis_link": "TRUE",
    }
    value.update(updates)
    return value


class ReviewStatusTests(unittest.TestCase):
    def test_pass(self):
        state = analysis_review_state(row())
        self.assertTrue(state.is_pass)
        self.assertEqual(state.row_label, "Pass")

    def test_one_issue(self):
        state = analysis_review_state(row(analysis_smart="FALSE"))
        self.assertEqual(state.issue_count, 1)
        self.assertEqual(state.row_label, "1 Issue")

    def test_any_two_issues_share_same_severity(self):
        a = analysis_review_state(row(analysis_feeder="FALSE", analysis_type="FALSE"))
        b = analysis_review_state(row(analysis_ip="FALSE", analysis_link="FALSE"))
        self.assertEqual(a.row_status, "two_issues")
        self.assertEqual(b.row_status, "two_issues")

    def test_name_is_always_critical(self):
        state = analysis_review_state(row(analysis_name="FALSE"))
        self.assertTrue(state.is_critical)
        self.assertEqual(state.row_label, "Critical / NAME")

    def test_three_or_more_are_critical(self):
        state = analysis_review_state(row(analysis_feeder="FALSE", analysis_smart="FALSE", analysis_ip="FALSE"))
        self.assertTrue(state.is_critical)

    def test_new_field_colors_exist(self):
        self.assertIsNotNone(field_false_color("IP"))
        self.assertIsNotNone(field_false_color("LINK"))


class RmuReviewPersistenceTests(unittest.TestCase):
    def test_explicit_rmu_review_status_is_persisted_and_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            try:
                self.assertEqual(store.rmu_review_map(), {})
                store.update_rmu_review_status("8664", "REVIEWED", "tester")
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "REVIEWED")
                change = store.changes()[0]
                self.assertEqual(change["rmu"], "8664")
                self.assertEqual(change["field_name"], "rmu_review_status")
                self.assertEqual(change["new_value"], "REVIEWED")
                store.update_rmu_review_status("8664", "UNREVIEWED", "tester")
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "UNREVIEWED")
            finally:
                store.db.close()

    def test_rmu_review_resets_only_when_automatic_analysis_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            try:
                base = {
                    "rmu": "8664", "no": 1,
                    "analysis_name": "TRUE", "analysis_feeder": "TRUE",
                    "analysis_smart": "TRUE", "analysis_type": "TRUE",
                    "analysis_ip": "TRUE", "analysis_link": "TRUE",
                    "analysis_link_detail": "linked",
                }
                store.save_comparison([dict(base)])
                store.update_rmu_review_status("8664", "REVIEWED", "tester")
                store.save_comparison([dict(base, se_station="changed-but-analysis-same")])
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "REVIEWED")

                changed = dict(base, analysis_link="FALSE", analysis_link_detail="not linked")
                store.save_comparison([changed])
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "UNREVIEWED")
                audit = [x for x in store.changes() if x["field_name"] == "rmu_review_status"]
                self.assertTrue(any("Automatic reset" in x["reason"] for x in audit))
            finally:
                store.db.close()

    def test_signal_review_resets_by_row_fingerprint_not_unrelated_source_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            try:
                store.update_db_smart_review(
                    row_key="signal-1", rmu="8664", field="review_status", value="REVIEWED",
                    modified_by="tester", source_hash="source-a", row_hash="row-a", site_name="ADF",
                )
                store.sync_db_smart_review_fingerprints({
                    "signal-1": {"source_hash": "source-b", "row_hash": "row-a"}
                })
                self.assertEqual(store.db_smart_review_map()["signal-1"]["review_status"], "REVIEWED")

                reset = store.sync_db_smart_review_fingerprints({
                    "signal-1": {"source_hash": "source-b", "row_hash": "row-b"}
                })
                self.assertEqual(reset, 1)
                review = store.db_smart_review_map()["signal-1"]
                self.assertEqual(review["review_status"], "UNREVIEWED")
                self.assertEqual(review["row_hash"], "row-b")
            finally:
                store.db.close()


if __name__ == "__main__":
    unittest.main()
