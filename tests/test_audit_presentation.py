import unittest

from migration_report_tool.services.audit_presentation import present_audit_item


class AuditPresentationTests(unittest.TestCase):
    def test_rmu_manual_review_is_business_readable(self):
        item = present_audit_item({
            "id": 1, "rmu": "26419", "field_name": "rmu_review_comment",
            "old_value": "", "new_value": "this is not good",
            "reason": "Optional RMU manual Review comment updated",
            "modified_by": "tester", "modified_at": "2026-08-23T21:55:01",
        })
        self.assertEqual(item["module"], "RMU Data Review")
        self.assertEqual(item["record"], "RMU 26419")
        self.assertEqual(item["field"], "Manual Review Comment")
        self.assertEqual(item["internal_field"], "rmu_review_comment")

    def test_structured_resolution_identifies_rmu_module_and_field(self):
        item = present_audit_item({
            "rmu": "9200", "field_name": "resolution.FEEDER",
            "old_value": "UNRESOLVED", "new_value": "Use SE = ABN-01",
            "reason": "Structured RMU Resolution decision",
        })
        self.assertEqual(item["module"], "RMU Data Review")
        self.assertEqual(item["field"], "Resolution · FEEDER")

    def test_signal_mapping_record_hides_internal_dbsmart_prefix(self):
        item = present_audit_item({
            "rmu": "DBSMART:5839", "field_name": "db_smart_review_status",
            "old_value": "UNREVIEWED", "new_value": "NEEDS ACTION",
            "reason": "Signal Mapping Human Review status changed",
        })
        self.assertEqual(item["module"], "Signal Mapping Review")
        self.assertEqual(item["record"], "RMU 5839")
        self.assertEqual(item["field"], "Review Status")

    def test_source_mapping_uses_source_and_canonical_field_label(self):
        item = present_audit_item({
            "rmu": "SCHEMA:zenon_db", "field_name": "source_mapping.rmu_type",
            "old_value": "", "new_value": "DEVICE", "reason": "Source schema override",
        })
        self.assertEqual(item["module"], "Site Data Sources")
        self.assertEqual(item["record"], "ZENON DB")
        self.assertEqual(item["field"], "Column Mapping · Equipment Type / Subtype")


if __name__ == "__main__":
    unittest.main()
