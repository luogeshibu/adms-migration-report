import unittest
import tempfile
from pathlib import Path

from migration_report_tool.storage import ProjectStore

from migration_report_tool.review_status import (
    analysis_review_state, field_false_color, signal_review_display_status, rmu_review_display_status,
)


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
        b = analysis_review_state(row(analysis_ip="FALSE", analysis_smart="FALSE", analysis_link="FALSE"))
        self.assertEqual(a.row_status, "two_issues")
        self.assertEqual(b.row_status, "two_issues")
        self.assertNotIn("LINK", b.false_fields)

    def test_one_and_two_issue_rows_share_one_visual_issue_color(self):
        one = analysis_review_state(row(analysis_feeder="FALSE"))
        two = analysis_review_state(row(analysis_feeder="FALSE", analysis_type="FALSE"))
        self.assertEqual(one.row_color, two.row_color)

    def test_all_false_fields_share_one_mismatch_color(self):
        colors = {field_false_color(name) for name in ("NAME", "FEEDER", "SMART", "TYPE", "IP")}
        self.assertEqual(len(colors), 1)
        self.assertIsNone(field_false_color("LINK"))

    def test_name_is_always_critical(self):
        state = analysis_review_state(row(analysis_name="FALSE"))
        self.assertTrue(state.is_critical)
        self.assertEqual(state.row_label, "Critical / NAME")

    def test_three_or_more_are_critical(self):
        state = analysis_review_state(row(analysis_feeder="FALSE", analysis_smart="FALSE", analysis_ip="FALSE"))
        self.assertTrue(state.is_critical)

    def test_new_field_colors_exist(self):
        self.assertIsNotNone(field_false_color("IP"))
        self.assertIsNone(field_false_color("LINK"))

    def test_signal_matched_defaults_closed_but_allows_three_explicit_states(self):
        self.assertEqual(signal_review_display_status("TRUE", "UNREVIEWED"), "CLOSED")
        self.assertEqual(signal_review_display_status("TRUE", "UNREVIEWED", explicit=True), "UNREVIEWED")
        self.assertEqual(signal_review_display_status("TRUE", "CLOSED"), "CLOSED")
        self.assertEqual(signal_review_display_status("TRUE", "NEEDS ACTION"), "NEEDS ACTION")
        # Legacy REVIEWED is normalized on read/migration to CLOSED.
        self.assertEqual(signal_review_display_status("TRUE", "REVIEWED"), "CLOSED")

    def test_signal_mismatch_defaults_unreviewed_and_accepts_explicit_states(self):
        self.assertEqual(signal_review_display_status("FALSE", "UNREVIEWED"), "UNREVIEWED")
        self.assertEqual(signal_review_display_status("FALSE", "CLOSED"), "CLOSED")
        self.assertEqual(signal_review_display_status("FALSE", "NEEDS ACTION"), "NEEDS ACTION")

    def test_signal_unchecked_stays_unreviewed_except_zenon_only_auto_close(self):
        self.assertEqual(signal_review_display_status("", "UNREVIEWED"), "UNREVIEWED")
        self.assertEqual(signal_review_display_status("", "UNREVIEWED", zenon_only=True), "CLOSED")
        self.assertEqual(signal_review_display_status("", "CLOSED"), "CLOSED")
        self.assertEqual(signal_review_display_status("", "NEEDS ACTION"), "NEEDS ACTION")

    def test_rmu_pass_defaults_closed_and_issue_defaults_unreviewed(self):
        self.assertEqual(rmu_review_display_status(row(), {}), "CLOSED")
        self.assertEqual(rmu_review_display_status(row(analysis_feeder="FALSE"), {}), "UNREVIEWED")
        self.assertEqual(
            rmu_review_display_status(row(), {"review_status": "UNREVIEWED", "reviewed_by": "tester"}),
            "UNREVIEWED",
        )


class RmuReviewPersistenceTests(unittest.TestCase):
    def test_explicit_rmu_review_status_is_persisted_and_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            try:
                self.assertEqual(store.rmu_review_map(), {})
                store.update_rmu_review_status("8664", "CLOSED", "tester")
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "CLOSED")
                change = store.changes()[0]
                self.assertEqual(change["rmu"], "8664")
                self.assertEqual(change["field_name"], "rmu_review_status")
                self.assertEqual(change["new_value"], "CLOSED")
                store.update_rmu_review_status("8664", "UNREVIEWED", "tester")
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "UNREVIEWED")
                self.assertTrue(store.rmu_review_map()["8664"]["reviewed_by"])
                store.update_rmu_review_status("8664", "NEEDS ACTION", "tester")
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "NEEDS ACTION")
            finally:
                store.db.close()

    def test_optional_rmu_manual_review_comment_is_persisted_and_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            try:
                store.update_rmu_manual_review_comment("8664", "Checked on site; no action required.", "tester")
                review = store.rmu_review_map()["8664"]
                self.assertEqual(review["manual_comment"], "Checked on site; no action required.")
                self.assertEqual(store.rmu_manual_review_comment("8664"), "Checked on site; no action required.")
                change = store.changes()[0]
                self.assertEqual(change["field_name"], "rmu_review_comment")
                self.assertEqual(change["new_value"], "Checked on site; no action required.")
                store.update_rmu_manual_review_comment("8664", "", "tester")
                self.assertEqual(store.rmu_manual_review_comment("8664"), "")
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
                store.update_rmu_review_status("8664", "CLOSED", "tester")
                store.save_comparison([dict(base, se_station="changed-but-analysis-same")])
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "CLOSED")

                # Retired LINK is no longer part of the active Analysis fingerprint.
                changed_link = dict(base, analysis_link="FALSE", analysis_link_detail="not linked")
                store.save_comparison([changed_link])
                self.assertEqual(store.rmu_review_map()["8664"]["review_status"], "CLOSED")

                # A change to an active Analysis field still resets the review.
                changed_ip = dict(base, analysis_ip="FALSE")
                store.save_comparison([changed_ip])
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
                    row_key="signal-1", rmu="8664", field="review_status", value="CLOSED",
                    modified_by="tester", source_hash="source-a", row_hash="row-a", site_name="ADF",
                )
                store.sync_db_smart_review_fingerprints({
                    "signal-1": {"source_hash": "source-b", "row_hash": "row-a"}
                })
                self.assertEqual(store.db_smart_review_map()["signal-1"]["review_status"], "CLOSED")

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


def test_closed_status_is_persisted_for_signal_rows():
    with tempfile.TemporaryDirectory() as tmp:
        store = ProjectStore(Path(tmp))
        try:
            store.update_db_smart_review(
                row_key="signal-closed", rmu="9001", field="review_status", value="CLOSED",
                modified_by="tester", source_hash="source-a", row_hash="row-a", site_name="ABH",
            )
            assert store.db_smart_review_map()["signal-closed"]["review_status"] == "CLOSED"
            change = store.changes()[0]
            assert change["field_name"] == "db_smart_review_status"
            assert change["new_value"] == "CLOSED"
        finally:
            store.db.close()


def test_explicit_signal_unreviewed_keeps_reviewer_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        store = ProjectStore(Path(tmp))
        try:
            store.update_db_smart_review(
                row_key="signal-clear", rmu="9002", field="review_status", value="CLOSED",
                modified_by="tester", source_hash="source-a", row_hash="row-a", site_name="ABH",
            )
            store.update_db_smart_review(
                row_key="signal-clear", rmu="9002", field="review_status", value="UNREVIEWED",
                modified_by="tester", source_hash="source-a", row_hash="row-a", site_name="ABH",
            )
            review = store.db_smart_review_map()["signal-clear"]
            assert review["review_status"] == "UNREVIEWED"
            assert review["reviewed_by"] == "tester"
            assert review["reviewed_at"]
        finally:
            store.db.close()
