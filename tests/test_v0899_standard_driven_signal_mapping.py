from pathlib import Path

from migration_report_tool.db_smart import (
    SIGNAL_MAPPING_COLUMNS,
    build_signal_mapping_report,
    signal_row_is_zenon_only,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _report():
    root = _root()
    return build_signal_mapping_report(
        root / "examples" / "sample-data" / "ZENON-ADMS-IOA.csv",
        root / "examples" / "sample-data" / "ADMS-SLD.csv",
        root / "resources" / "templates" / "IOA STANDARD.xlsx",
    )


def _index():
    return {key: i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)}


def test_signal_mapping_display_and_engine_order_is_standard_adms_zenon():
    report = _report()
    groups = [name for name, _color, _columns in report.group_definitions]
    assert report.sheet_name == "Calculated · STANDARD → ADMS validation + ZENON implementation hint"
    assert groups.index("STANDARD DATABASE I/O list") < groups.index("ADMS") < groups.index("ZENON")
    summary_keys = [key for group, _color, columns in report.group_definitions if group == "Comparison Summary" for key, _label, _width in columns]
    assert summary_keys == ["summary_item", "summary_adms_standard"]


def test_sample_standard_driven_counts_are_reconciled():
    report = _report()
    index = _index()
    true_count = sum(row.values[report.analysis_column] == "TRUE" for row in report.rows)
    false_count = sum(row.values[report.analysis_column] == "FALSE" for row in report.rows)
    standard_count = sum(bool(row.values[index["standard_dot_no"]]) for row in report.rows)
    adms_count = sum(bool(row.values[index["adms_dot_no"]]) for row in report.rows)
    assert standard_count == 5524
    assert adms_count == 5526
    assert true_count == 5520
    assert false_count == 10


def test_false_rows_cover_standard_missing_and_adms_extra():
    report = _report()
    index = _index()
    false_rows = [row for row in report.rows if row.values[report.analysis_column] == "FALSE"]
    assert any(row.values[index["standard_dot_no"]] and not row.values[index["adms_dot_no"]] for row in false_rows)
    assert any(row.values[index["adms_dot_no"]] and not row.values[index["standard_dot_no"]] for row in false_rows)


def test_zenon_extra_keeps_semantic_adms_implementation_lookup():
    report = _report()
    index = _index()
    row = next(
        item for item in report.rows
        if item.rmu == "16781" and item.values[index["zenon_signal_name"]] == "16781_TR1_KVAR"
    )
    assert signal_row_is_zenon_only(row)
    assert "16781 Q1 Q(kVar)" in row.suggested_comment
    assert "TR1→Q1 + KVAR" in row.suggested_comment


def test_signal_ui_has_no_automatic_unchecked_state():
    ui = (_root() / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'MetricCard("Unchecked"' not in ui
    assert '"UNCHECKED"' not in ui
    assert 'MetricCard("ZENON Extra"' in ui
    assert '["ALL RESULTS", "MATCHED", "MISMATCHED", "ZENON EXTRA"]' in ui
