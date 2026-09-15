import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'src/migration_report_tool/ui/main_window.py').read_text(encoding='utf-8')
VERSION = (ROOT / 'src/migration_report_tool/version.py').read_text(encoding='utf-8')


class V08195CustomResolutionSaveFixTests(unittest.TestCase):
    def test_version(self):
        self.assertIn('__version__ = "0.8.196"', VERSION)

    def test_other_branch_resolves_field_label_before_description(self):
        start = UI.index('    def decisions(self) -> dict[str, dict | None]:')
        end = UI.index('\n\nclass ColumnVisibilityDialog', start)
        block = UI[start:end]
        other = block.index('if decision == "OTHER":')
        label = block.index('field_label = self._field_label(field)', other)
        build = block.index('field=field_label, decision_type="OTHER"', other)
        self.assertLess(label, build)

    def test_other_branch_keeps_custom_resolution_and_customer_comment_independent(self):
        start = UI.index('    def decisions(self) -> dict[str, dict | None]:')
        end = UI.index('\n\nclass ColumnVisibilityDialog', start)
        block = UI[start:end]
        self.assertIn('"selected_value": comment', block)
        self.assertIn('payload["customer_comment"] = new_comment if new_comment else existing_comment', block)
        self.assertIn('payload["customer_comment_submitted"] = bool(new_comment)', block)
        self.assertIn('payload["issue_snapshot"] = dict(self.issue_snapshots.get(field) or {})', block)


if __name__ == '__main__':
    unittest.main()

class V08195CustomResolutionPersistenceTests(unittest.TestCase):
    def test_other_custom_resolution_and_customer_comment_persist_together(self):
        import tempfile
        from pathlib import Path
        from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore

        row = {
            "rmu": "12650",
            "analysis_name": "TRUE",
            "analysis_feeder": "FALSE",
            "analysis_smart": "TRUE",
            "analysis_type": "TRUE",
            "analysis_ip": "TRUE",
            "analysis_feeder_detail": "SE AJWD-06 vs ZENON DB HNM-06",
            "resolution_candidates": {
                "FEEDER": [
                    {"source": "SE", "value": "AJWD-06", "normalized": "AJWD-06"},
                    {"source": "ZENON DB", "value": "HNM-06", "normalized": "HNM-06"},
                ]
            },
        }
        decisions = {
            "FEEDER": {
                "decision_type": "OTHER",
                "selected_source": "Others",
                "selected_value": "Use field-confirmed feeder HNM-06",
                "normalized_value": "",
                "decision_description": "Custom feeder instruction",
                "customer_comment": "Customer confirms the correction",
                "customer_comment_submitted": True,
                "issue_snapshot": {"analysis_field": "FEEDER", "analysis_result": "FALSE"},
            }
        }
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                status, _ = store.save_rmu_resolution_decisions("12650", row, decisions, "tester")
                self.assertEqual(status, "UNREVIEWED")
                saved = store.rmu_resolution_map("12650")["FEEDER"]
                self.assertEqual(saved["decision_type"], "OTHER")
                self.assertEqual(saved["selected_value"], "Use field-confirmed feeder HNM-06")
                self.assertEqual(saved["customer_comment"], "Customer confirms the correction")
                events = [
                    e for e in store.rmu_review_events("12650")
                    if e["analysis_field"] == "FEEDER" and e["event_type"] == "RESOLUTION_COMMENT_RECORDED"
                ]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["comment"], "Customer confirms the correction")
            finally:
                store.close()
