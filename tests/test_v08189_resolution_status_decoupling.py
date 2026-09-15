from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore


class ResolutionStatusDecouplingTests(unittest.TestCase):
    @staticmethod
    def _row() -> dict:
        return {
            "no": 1,
            "rmu": "EQ-1001",
            "analysis_name": "TRUE",
            "analysis_feeder": "FALSE",
            "analysis_smart": "TRUE",
            "analysis_type": "TRUE",
            "analysis_ip": "TRUE",
            "analysis_feeder_detail": "SE: B416 / ADMS DB: B420",
            "resolution_candidates": {
                "FEEDER": [
                    {"source": "SE", "value": "B416", "normalized": "B416"},
                    {"source": "ADMS DB", "value": "B420", "normalized": "B420"},
                ]
            },
            "status": "FAILED",
            "remarks": "Analysis mismatch: FEEDER",
            "comments": "",
        }

    def test_adms_db_resolution_does_not_close_manual_needs_action(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                row = self._row()
                store.save_comparison([row])
                store.update_rmu_review_status(
                    "EQ-1001", "NEEDS ACTION", "tester", "Reviewer explicitly requires follow-up"
                )
                adms = row["resolution_candidates"]["FEEDER"][1]
                status, _ = store.save_rmu_resolution_decisions(
                    "EQ-1001",
                    row,
                    {
                        "FEEDER": {
                            "decision_type": "USE_SOURCE",
                            "selected_source": adms["source"],
                            "selected_value": adms["value"],
                            "normalized_value": adms["normalized"],
                        }
                    },
                    "tester",
                )
                self.assertEqual(status, "NEEDS ACTION")
                self.assertEqual(store.rmu_review_record("EQ-1001")["review_status"], "NEEDS ACTION")
                self.assertEqual(store.rmu_action_tracking(status="OPEN")[0]["rmu"], "EQ-1001")
            finally:
                store.close()

    def test_resolution_choices_never_open_or_close_review_status(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                row = self._row()
                store.save_comparison([row])
                se = row["resolution_candidates"]["FEEDER"][0]
                status, _ = store.save_rmu_resolution_decisions(
                    "EQ-1001",
                    row,
                    {
                        "FEEDER": {
                            "decision_type": "USE_SOURCE",
                            "selected_source": se["source"],
                            "selected_value": se["value"],
                            "normalized_value": se["normalized"],
                        }
                    },
                    "tester",
                )
                self.assertEqual(status, "UNREVIEWED")

                store.update_rmu_review_status("EQ-1001", "CLOSED", "tester", "Explicit closure")
                adms = row["resolution_candidates"]["FEEDER"][1]
                status, _ = store.save_rmu_resolution_decisions(
                    "EQ-1001",
                    row,
                    {
                        "FEEDER": {
                            "decision_type": "USE_SOURCE",
                            "selected_source": adms["source"],
                            "selected_value": adms["value"],
                            "normalized_value": adms["normalized"],
                        }
                    },
                    "tester",
                )
                self.assertEqual(status, "CLOSED")
                self.assertEqual(store.rmu_review_record("EQ-1001")["review_status"], "CLOSED")
            finally:
                store.close()

    def test_ui_help_states_review_status_is_manual(self):
        root = Path(__file__).resolve().parents[1]
        ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Resolution choices record the agreed handling only and never change Review Status.", ui)
        self.assertNotIn("choosing the same normalized value closes the equipment review", ui)


if __name__ == "__main__":
    unittest.main()
