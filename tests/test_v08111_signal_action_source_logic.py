import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py"
PDF = PDF_PATH.read_text(encoding="utf-8")
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
        "_signal_register_point_no",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=nodes, type_ignores=[])
    def _parse_structured(value):
        text = _clean(value)
        match = re.match(r"^(ADD|MODIFY|DELETE)\s*\|\s*(.+)$", text, re.I | re.S)
        if match:
            return match.group(1).upper(), match.group(2).strip()
        return "", text

    ns = {"clean": _clean, "re": re, "parse_signal_action_comment": _parse_structured}
    exec(compile(module, str(PDF_PATH), "exec"), ns)
    return ns


def test_signal_action_is_source_structure_first_not_comment_keyword_first():
    h = _load_signal_helpers()
    action = h["_signal_action_label"]

    # STANDARD requires a point but ADMS is missing: always ADD, even if a
    # misleading free-text comment contains a different verb.
    assert action({
        "standard_signal": "Y1 CMD", "standard_dot": "1008",
        "adms_signal": "", "adms_dot": "",
        "user_comment": "please modify later",
        "analysis": "FALSE",
    }) == "ADD"

    # ADMS contains a point that STANDARD does not define: DELETE.
    assert action({
        "standard_signal": "", "standard_dot": "",
        "adms_signal": "Y1 CMD", "adms_dot": "1008",
        "user_comment": "please add a note",
        "analysis": "FALSE",
    }) == "DELETE"

    # Existing STANDARD/ADMS point with a failed comparison: MODIFY.
    assert action({
        "standard_signal": "Y1 CMD", "standard_dot": "1008",
        "adms_signal": "Y1 STATUS", "adms_dot": "1008",
        "analysis": "FALSE",
    }) == "MODIFY"


def test_fully_matched_manual_need_action_is_concrete_modify():
    h = _load_signal_helpers()
    action = h["_signal_action_label"]
    assert action({
        "standard_signal": "Y1 CMD", "standard_dot": "1008",
        "adms_signal": "Y1 CMD", "adms_dot": "1008",
        "analysis": "TRUE",
    }) == "MODIFY"


def test_zenon_only_need_action_uses_concrete_add_modify_delete():
    h = _load_signal_helpers()
    action = h["_signal_action_label"]
    row = {"zenon_signal": "TR1 KVAR", "zenon_dot": "14001"}
    assert action(row) == "ADD"
    assert action({**row, "suggested_comment": "ADMS implementation: Q1 Q(kVar) | ADMS DOT 14003."}) == "MODIFY"
    assert action({**row, "user_comment": "remove this point"}) == "DELETE"


def test_signal_pdf_remarks_merge_auto_text_and_user_comment():
    h = _load_signal_helpers()
    action = h["_signal_action_label"]
    auto = h["_signal_auto_resolution_text"]
    combined = h["_signal_combined_remarks"]

    item = {
        "standard_signal": "Y1 CMD", "standard_dot": "1008",
        "adms_signal": "Y1 STATUS", "adms_dot": "1008",
        "analysis": "FALSE",
        "user_comment": "Confirmed with site team.",
    }
    item["action"] = action(item)
    item["auto_remark"] = auto(item)
    remarks = combined(item)
    assert "modify ADMS to the STANDARD value" in remarks
    assert "User comment: Confirmed with site team." in remarks


def test_add_uses_standard_point_and_delete_modify_use_adms_point():
    h = _load_signal_helpers()
    point = h["_signal_register_point_no"]
    assert point({"action": "ADD", "standard_dot": "1008", "zenon_dot": "9008"}) == "1008"
    assert point({"action": "DELETE", "adms_dot": "1005", "standard_dot": "1008"}) == "1005"
    assert point({"action": "MODIFY", "adms_dot": "1003", "standard_dot": "1003"}) == "1003"
    assert point({"action": "MODIFY", "zenon_dot": "13", "suggested_comment": "ADMS implementation: Y2 CMD | ADMS DOT 9 | GSS-FID X."}) == "9"


def test_snapshot_persists_action_auto_remark_and_combined_remarks():
    start = PDF.index("def _signal_need_action_snapshot")
    end = PDF.index("def _signal_validation_summary", start)
    block = PDF[start:end]
    assert 'item["action"] = _signal_action_label(item)' in block
    assert 'item["auto_remark"] = _signal_auto_resolution_text(item)' in block
    assert 'item["required_action"] = _signal_combined_remarks(item)' in block
    assert '"user_comment": clean(review.get("comments"))' in block


def test_pdf_explains_signal_action_contract_and_release_version():
    assert "missing ADMS = ADD, extra ADMS = DELETE, existing STANDARD/ADMS pair = MODIFY" in PDF
    assert '__version__ = "0.8.120"' in VERSION
