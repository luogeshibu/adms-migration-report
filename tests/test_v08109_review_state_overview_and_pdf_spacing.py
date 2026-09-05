from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_signal_overview_color_follows_review_state_not_raw_mismatch():
    start = UI.index("def _render_db_smart_rmu_list")
    end = UI.index("def _show_db_smart_rmu_overview", start)
    block = UI[start:end]
    assert 'has_unreviewed = bool(metric.get("unreviewed", 0))' in block
    assert 'has_unreviewed_mismatch = bool(metric.get("unreviewed_mismatch", 0))' in block
    assert 'elif has_unreviewed:' in block
    assert 'fill = QColor("#FFF8E6")' in block
    assert 'fill = QColor("#EAF7F0")' in block
    assert 'has_mismatch = bool(metric["mismatched"])' not in block


def test_closed_false_can_be_green_in_overview_but_detail_false_rule_is_unchanged():
    metrics = UI[UI.index("def _db_smart_rmu_metrics_map"):UI.index("def _db_smart_rmu_metrics", UI.index("def _db_smart_rmu_metrics_map") + 10)]
    assert 'item["unreviewed_mismatch"] += result == "FALSE" and status == "UNREVIEWED"' in metrics
    assert 'item["closed"] += status == "CLOSED"' in metrics
    assert '"FALSE"' in UI and '#D92D20' in UI


def test_lazy_signal_fingerprint_sync_uses_report_parameter():
    start = UI.index("def _sync_signal_review_fingerprints")
    end = UI.index("def _set_workflow_badge", start)
    block = UI[start:end]
    assert 'signal_review_alias_map(report)' in block
    assert 'signal_review_metadata(report, item)' in block
    assert 'signal_review_alias_map(signal_report)' not in block


def test_pdf_verification_order_boxes_and_signoff_spacing():
    assert '<th>Remarks</th><th>NARI Confirm</th><th>SE/DNV Verify</th>' in PDF
    assert '&#9633;' in PDF
    assert '&#10003;' in PDF and '&#10007;' in PDF
    assert '.signoff-block + .signoff-block {{ margin-top:46px; padding-top:8px; }}' in PDF


def test_release_version():
    assert '__version__ = "0.8.120"' in VERSION
