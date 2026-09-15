from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import discover_site_sources
from migration_report_tool.version import __version__


class V08173SourceChangeLifecycleTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_semantic_version_beats_newer_unversioned_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "1-ABN2"
            site.mkdir()
            base = site / "ADMS-SLD.xlsx"
            v1 = site / "ADMS-SLD-V1.xlsx"
            base.write_bytes(b"base")
            v1.write_bytes(b"v1")
            # The base file is deliberately newer on disk. AUTO must still use
            # the explicit semantic V version; mtimes are only a tie-breaker.
            os.utime(v1, (1000, 1000))
            os.utime(base, (2000, 2000))
            sources, _detections, _unmapped = discover_site_sources(site, deep=False)
            self.assertEqual(sources["adms_sld"].name, "ADMS-SLD-V1.xlsx")

    def test_only_changed_source_values_are_appended_for_need_action_equipment(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                old_context = {
                    "adms_sld": {"name": "ADMS-SLD.xlsx", "sha256": "old", "size": 100, "mtime_ns": 1},
                    "adms_db": {"name": "ADMS-DB.csv", "sha256": "dbsame", "size": 100, "mtime_ns": 1},
                }
                new_context = {
                    "adms_sld": {"name": "ADMS-SLD-V1.xlsx", "sha256": "new", "size": 110, "mtime_ns": 2},
                    "adms_db": {"name": "ADMS-DB.csv", "sha256": "dbsame", "size": 100, "mtime_ns": 1},
                }
                first = [
                    {"no": 1, "rmu": "1001", "asld_type": "2L1T", "adb_gss_fid": "ABN-01", "_source_context": old_context},
                    {"no": 2, "rmu": "2002", "asld_type": "2L1T", "adb_gss_fid": "ABN-02", "_source_context": old_context},
                ]
                store.save_comparison(first)
                store.update_rmu_review_status("1001", "NEEDS ACTION", "tester")

                second = [
                    # Only TYPE changed for 1001. FEEDER did not change and must
                    # not generate a lifecycle event.
                    {"no": 1, "rmu": "1001", "asld_type": "3L1T", "adb_gss_fid": "ABN-01", "_source_context": new_context},
                    # 2002 changed too, but it never had Needs Action history and
                    # therefore must not enter the lifecycle tracker.
                    {"no": 2, "rmu": "2002", "asld_type": "3L1T", "adb_gss_fid": "ABN-02", "_source_context": new_context},
                ]
                store.save_comparison(second)

                events_1001 = [
                    event for event in store.rmu_full_lifecycle("1001")["events"]
                    if str(event.get("event_type") or "").upper() == "SOURCE_VALUE_CHANGED"
                ]
                self.assertEqual(len(events_1001), 1)
                event = events_1001[0]
                self.assertEqual(event["field_name"], "ADMS SLD · TYPE")
                self.assertEqual(event["old_value"], "2L1T")
                self.assertEqual(event["new_value"], "3L1T")
                self.assertIn("ADMS-SLD.xlsx -> ADMS-SLD-V1.xlsx", event["reason"])

                events_2002 = [
                    event for event in store.rmu_full_lifecycle("2002")["events"]
                    if str(event.get("event_type") or "").upper() == "SOURCE_VALUE_CHANGED"
                ]
                self.assertEqual(events_2002, [])
            finally:
                store.close()

    def test_same_source_identity_does_not_create_false_source_change_history(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                context = {
                    "adms_sld": {"name": "ADMS-SLD-V1.xlsx", "sha256": "same", "size": 100, "mtime_ns": 1}
                }
                store.save_comparison([
                    {"no": 1, "rmu": "1001", "asld_type": "2L1T", "_source_context": context}
                ])
                store.update_rmu_review_status("1001", "NEEDS ACTION", "tester")
                # Simulate a mapping-only recalculation while the physical source
                # identity is unchanged. It must not be logged as a file change.
                store.save_comparison([
                    {"no": 1, "rmu": "1001", "asld_type": "3L1T", "_source_context": context}
                ])
                events = [
                    event for event in store.rmu_full_lifecycle("1001")["events"]
                    if str(event.get("event_type") or "").upper() == "SOURCE_VALUE_CHANGED"
                ]
                self.assertEqual(events, [])
            finally:
                store.close()


    def test_same_filename_refreshed_content_is_tracked_by_hash(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                old_context = {
                    "adms_db": {"name": "ADMS-DB.csv", "sha256": "sha-old", "size": 100, "mtime_ns": 1}
                }
                new_context = {
                    "adms_db": {"name": "ADMS-DB.csv", "sha256": "sha-new", "size": 101, "mtime_ns": 2}
                }
                store.save_comparison([
                    {"no": 1, "rmu": "3003", "adb_gss_fid": "ABN-01", "_source_context": old_context}
                ])
                store.update_rmu_review_status("3003", "NEEDS ACTION", "tester")
                store.save_comparison([
                    {"no": 1, "rmu": "3003", "adb_gss_fid": "ABN-02", "_source_context": new_context}
                ])
                events = [
                    event for event in store.rmu_full_lifecycle("3003")["events"]
                    if str(event.get("event_type") or "").upper() == "SOURCE_VALUE_CHANGED"
                ]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["field_name"], "ADMS DB · FEEDER")
                self.assertEqual(events[0]["old_value"], "ABN-01")
                self.assertEqual(events[0]["new_value"], "ABN-02")
                self.assertIn("ADMS-DB.csv refreshed", events[0]["reason"])
            finally:
                store.close()

    def test_source_change_after_case_closed_appends_without_reopening_case(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                old_context = {
                    "adms_sld": {"name": "ADMS-SLD-V1.xlsx", "sha256": "v1", "size": 100, "mtime_ns": 1}
                }
                new_context = {
                    "adms_sld": {"name": "ADMS-SLD-V2.xlsx", "sha256": "v2", "size": 120, "mtime_ns": 2}
                }
                store.save_comparison([
                    {"no": 1, "rmu": "4004", "asld_type": "2L1T", "_source_context": old_context}
                ])
                store.update_rmu_review_status("4004", "NEEDS ACTION", "tester")
                store.update_rmu_review_status("4004", "CLOSED", "tester")
                store.save_comparison([
                    {"no": 1, "rmu": "4004", "asld_type": "3L1T", "_source_context": new_context}
                ])

                lifecycle = store.rmu_full_lifecycle("4004")
                rmu_cases = [c for c in lifecycle["cases"] if str(c.get("entity_type") or "").upper() == "RMU"]
                self.assertEqual(len(rmu_cases), 1)
                self.assertEqual(str(rmu_cases[0]["status"]).upper(), "CLOSED")
                source_events = [
                    event for event in lifecycle["events"]
                    if str(event.get("event_type") or "").upper() == "SOURCE_VALUE_CHANGED"
                ]
                self.assertEqual(len(source_events), 1)
                self.assertEqual(source_events[0]["case_no"], 1)
                self.assertEqual(source_events[0]["event_state"], "CLOSED")
                self.assertEqual(source_events[0]["field_name"], "ADMS SLD · TYPE")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
