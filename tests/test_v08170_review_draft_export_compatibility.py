from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


class ReviewDraftExportCompatibilityTests(unittest.TestCase):
    def test_release_version(self):
        self.assertIn('__version__ = "0.8.196"', VERSION)

    def test_validation_pending_is_confirmation_not_hard_gate(self):
        helper_start = UI.index("    def _confirm_review_draft_export")
        signoff_start = UI.index("    def export_signoff_pdf", helper_start)
        excel_start = UI.index("    def export_excel", signoff_start)
        signoff_block = UI[signoff_start:excel_start]
        excel_block = UI[excel_start:UI.index("    def open_folder", excel_start)]

        self.assertIn('_confirm_review_draft_export("PDF")', signoff_block)
        self.assertIn('_confirm_review_draft_export("Excel")', excel_block)
        self.assertNotIn('"Run Validation first. The PDF is only generated', signoff_block)
        self.assertNotIn('"Run Validation first. The Excel report is only exported', excel_block)
        self.assertIn("QMessageBox.question", UI[helper_start:signoff_start])
        self.assertIn("most recently calculated review data", UI[helper_start:signoff_start])

    def test_no_calculated_rows_still_block_export(self):
        signoff_start = UI.index("    def export_signoff_pdf")
        excel_start = UI.index("    def export_excel", signoff_start)
        self.assertIn("if self.store.comparison_row_count() <= 0:", UI[signoff_start:excel_start])
        self.assertIn("if self.store.comparison_row_count() <= 0:", UI[excel_start:UI.index("    def open_folder", excel_start)])

    def test_draft_pdf_is_visibly_and_persistently_identified(self):
        self.assertIn("review_draft: bool = False", PDF)
        self.assertIn('snapshot["document_status"] = "REVIEW DRAFT" if review_draft else "FORMAL"', PDF)
        self.assertIn('snapshot["validation_required_at_export"]', PDF)
        self.assertIn('REVIEW DRAFT · VALIDATION REQUIRED · NOT FOR FINAL HANDOVER / SIGNATURE', PDF)
        self.assertIn('draft_token = "_DRAFT" if review_draft else ""', PDF)
        self.assertIn("review_draft=review_draft", UI)
        self.assertIn('report_type="SITE_SIGNOFF_DRAFT" if review_draft else "SITE_SIGNOFF"', UI)

    def test_draft_pdf_cannot_be_attached_as_formal_signed_copy(self):
        attach_start = UI.index("    def attach_signed_signoff_pdf")
        attach_end = UI.index("    def open_selected_signoff_pdf", attach_start)
        block = UI[attach_start:attach_end]
        self.assertIn('document_status', block)
        self.assertIn('REVIEW DRAFT', block)
        self.assertIn('Review draft cannot be signed', block)


if __name__ == "__main__":
    unittest.main()
