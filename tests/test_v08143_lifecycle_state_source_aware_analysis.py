from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import resolve_schema
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.storage import ProjectStore
from migration_report_tool.version import __version__


class DictAdapter(SourceAdapter):
    def __init__(self, data: dict[str, list[dict]]):
        self.data = data

    def load_rows(self, source_type: str) -> list[dict]:
        return [dict(row) for row in self.data.get(source_type, [])]


class LifecycleStateAndSourceAwareAnalysisV08143Tests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_rmu_timeline_uses_state_at_event_not_final_case_status(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                store.update_rmu_review_status("30825", "NEEDS ACTION", "alice", "Feeder mismatch")
                store.update_rmu_manual_review_comment("30825", "Confirm with site", "bob")
                store.update_rmu_review_status("30825", "UNREVIEWED", "carol", "Waiting for customer")
                store.update_rmu_review_status("30825", "CLOSED", "dave", "Approved and corrected")

                payload = store.rmu_full_lifecycle("30825")
                self.assertEqual(payload["case_count"], 1)
                self.assertEqual(payload["cases"][0]["status"], "CLOSED")

                events = payload["events"]
                self.assertEqual(events[0]["event_type"], "CASE_OPENED")
                self.assertEqual(events[0]["case_status"], "CLOSED")  # final formal case state
                self.assertEqual(events[0]["event_state"], "NEEDS ACTION")
                self.assertEqual(events[1]["event_state"], "NEEDS ACTION")
                self.assertTrue(any(e["event_state"] == "UNREVIEWED" for e in events))
                self.assertEqual(events[-1]["event_type"], "CASE_CLOSED")
                self.assertEqual(events[-1]["event_state"], "CLOSED")
            finally:
                store.close()

    def test_all_analysis_fields_ignore_blanks_and_one_available_value_is_true(self):
        data = {
            "se_list": [{"rmu": "30825", "feeder": "ABH-12", "smart": "SMART", "rmu_type": "3L1T"}],
            "zenon_db": [],
            "zenon_sld": [],
            "adms_db": [],
            "adms_sld": [],
        }
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                store.config["repository_site"] = "1-ABH"
                rows, _summary = build_comparison(store, DictAdapter(data))
                self.assertEqual(len(rows), 1)
                row = rows[0]
                self.assertEqual(row["analysis_name"], "TRUE")
                self.assertEqual(row["analysis_feeder"], "TRUE")
                self.assertEqual(row["analysis_smart"], "TRUE")
                self.assertEqual(row["analysis_type"], "TRUE")
                self.assertEqual(row["analysis_ip"], "")
                self.assertEqual(row["status"], "MATCHED")
                self.assertIn("ignored by Analysis", row["remarks"])
            finally:
                store.close()

    def test_ip_analysis_uses_every_available_rmu_source_and_detects_mismatch(self):
        same_ip = "172.20.13.10"
        data = {
            "se_list": [{"rmu": "30825", "feeder": "ABH-12", "ip": same_ip}],
            "zenon_db": [{"rmu": "30825", "feeder": "ABH-12", "ip": same_ip}],
            "zenon_sld": [{"rmu": "30825", "feeder": "ABH-12", "ip": same_ip}],
            "adms_db": [{"rmu": "30825", "gss_fid": "ABH-AH312", "channel_ip": same_ip}],
            "adms_sld": [{"rmu": "30825", "feeder": "ABH-12", "ip": same_ip}],
        }
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                store.config["repository_site"] = "1-ABH"
                rows, _ = build_comparison(store, DictAdapter(data))
                self.assertEqual(rows[0]["analysis_ip"], "TRUE")
                candidates = rows[0]["resolution_candidates"]["IP"]
                self.assertEqual({c["source"] for c in candidates}, {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"})

                data["adms_sld"][0]["ip"] = "172.20.13.99"
                rows, _ = build_comparison(store, DictAdapter(data))
                self.assertEqual(rows[0]["analysis_ip"], "FALSE")
                self.assertIn("ADMS SLD=172.20.13.99", rows[0]["remarks"])
            finally:
                store.close()

    def test_optional_ip_header_is_ready_on_future_sources(self):
        for source_type, headers in (
            ("se_list", ["EQUIPMENT", "FEEDER", "IP"]),
            ("zenon_sld", ["RMU", "FEEDER", "IP"]),
            ("adms_sld", ["环网柜名称", "IP"]),
        ):
            with self.subTest(source_type=source_type):
                result = resolve_schema(schema_for(source_type), headers)
                self.assertFalse(result.errors)
                self.assertEqual(result.mapped_column("ip"), "IP")

    def test_ui_labels_event_state_separately_from_final_case_status(self):
        source = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        self.assertIn('"State at Event"', source)
        self.assertIn('"Final Status"', source)
        self.assertIn('event.get("event_state")', source)


if __name__ == "__main__":
    unittest.main()
