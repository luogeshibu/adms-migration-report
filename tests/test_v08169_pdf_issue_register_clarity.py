import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


class TestV08169PdfIssueRegisterClarity(unittest.TestCase):
    def test_release_version(self):
        self.assertIn('__version__ = "0.8.196"', VERSION)

    def test_rmu_register_uses_issue_type_not_review_status_as_column(self):
        self.assertIn("<th>Issue Type</th>", PDF)
        self.assertNotIn("<th>Modification Item</th>", PDF)
        self.assertIn('issue_type=_field_label(row, field)', PDF)
        self.assertIn("_infer_manual_issue_types", PDF)
        self.assertIn('return result or ["MANUAL REVIEW"]', PDF)

    def test_one_issue_per_rmu_row_to_avoid_tall_multiline_rows(self):
        block = PDF[PDF.index("def _rmu_open_action_snapshot"):PDF.index("def build_site_signoff_snapshot")]
        self.assertIn("for field_index, field in enumerate(issue_fields):", block)
        self.assertIn("result.append(_action_row(", block)
        self.assertNotIn('issue_fields = ["Needs Action"]', block)

    def test_ambiguous_tbd_is_removed_from_formal_pdf_source(self):
        self.assertNotIn("TBD", PDF)
        self.assertIn("Not specified", PDF)
        self.assertIn("Not available in ADMS DB", PDF)
        self.assertIn("See Remarks", PDF)

    def test_pdf_rows_are_kept_together_and_headers_repeat(self):
        self.assertIn(".grid thead {{ display:table-header-group; }}", PDF)
        self.assertIn(".grid tr {{ page-break-inside:avoid; break-inside:avoid; }}", PDF)
        self.assertIn(".grid thead tr {{ page-break-after:avoid; break-after:avoid; }}", PDF)

    def test_manual_comment_issue_type_inference_covers_common_fields(self):
        for label in ("FEEDER", "SMART", "TYPE", "IP", "BRAND", "DEVICE DATA", "SOURCE DATA"):
            self.assertIn(f'add("{label}")', PDF)


if __name__ == "__main__":
    unittest.main()
