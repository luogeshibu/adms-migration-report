import ast
import re
from pathlib import Path

from migration_report_tool.domain.analysis.signal_action_comment import (
    format_signal_action_comment,
    parse_signal_action_comment,
)

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py"
PDF = PDF_PATH.read_text(encoding="utf-8")
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def _clean(value):
    return "" if value is None else str(value).strip()


def _load_signal_helpers():
    tree = ast.parse(PDF)
    wanted = {
        "_signal_source_present",
        "_signal_explicit_comment_action",
        "_signal_action_label",
        "_signal_label",
        "_signal_auto_resolution_text",
        "_signal_combined_remarks",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=nodes, type_ignores=[])
    ns = {
        "clean": _clean,
        "re": re,
        "parse_signal_action_comment": parse_signal_action_comment,
    }
    exec(compile(module, str(PDF_PATH), "exec"), ns)
    return ns


def test_comments_store_action_and_required_remark_together():
    stored = format_signal_action_comment("modify", "Align the ADMS point with approved STANDARD.")
    assert stored == "MODIFY | Align the ADMS point with approved STANDARD."
    assert parse_signal_action_comment(stored) == (
        "MODIFY", "Align the ADMS point with approved STANDARD."
    )


def test_structured_manual_action_drives_pdf_action_and_remark():
    h = _load_signal_helpers()
    item = {
        "standard_signal": "Y1 CMD",
        "standard_dot": "1008",
        "adms_signal": "Y1 CMD",
        "adms_dot": "1008",
        "user_comment": "DELETE | Remove the duplicate point after field confirmation.",
    }
    assert h["_signal_action_label"](item) == "DELETE"
    assert h["_signal_combined_remarks"](item) == "Remove the duplicate point after field confirmation."


def test_signal_register_sorts_by_effective_point_number_ascending():
    start = PDF.index("def _signal_need_action_rows")
    end = PDF.index("def _display_revision_name", start)
    block = PDF[start:end]
    assert "point_sort_key" in block
    assert "float(raw)" in block
    assert "items.sort(key=point_sort_key)" in block
    assert block.index("items.sort(key=point_sort_key)") < block.index("for idx, item in enumerate(items, 1)")


def test_signal_action_remark_dialog_is_mandatory_and_marks_need_action():
    assert "class SignalActionRemarkDialog" in UI
    assert 'QPushButton("Action / Remark")' in UI
    assert "Select ADD / MODIFY / DELETE and enter a remark before saving." in UI
    assert 'field="review_status", value="NEEDS ACTION"' in UI
    assert "Both are saved in Comments" in UI


def test_pdf_verification_columns_are_swapped_without_other_schema_changes():
    assert "<th>NARI Confirm</th><th>SE/DNV Verify</th>" in PDF
    assert "<th>SE/DNV Verify</th><th>NARI Confirm</th>" not in PDF
    assert "<th>Point No.</th><th>Action</th><th>Remarks</th>" in PDF


def test_release_version_is_08116():
    assert '__version__ = "0.8.120"' in VERSION
