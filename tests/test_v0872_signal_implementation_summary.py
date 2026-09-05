# v0.8.72 tests
from pathlib import Path

from migration_report_tool.domain.mapping.signal_mapping import (
    build_signal_mapping_report,
    SIGNAL_MAPPING_COLUMNS,
    zenon_only_adms_match_rows,
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


def _row(report, rmu: str, zenon_name: str):
    index = {key: i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)}
    zenon_index = index["zenon_signal_name"]
    return next(
        row for row in report.rows
        if row.rmu == rmu and zenon_index < len(row.values) and row.values[zenon_index] == zenon_name
    )


def test_zenon_only_match_rows_returns_actual_adms_y1_kvar_row():
    report = _report()
    source = _row(report, "16781", "16781_Y1-16782_KVAR")
    matches = zenon_only_adms_match_rows(source, report.rows)
    assert matches
    assert any("16781 Y1 Q(kVar)" in row.values for row in matches)
    assert any("13059" in row.values for row in matches)


def test_zenon_only_match_rows_applies_tr_to_q_lookup():
    report = _report()
    source = _row(report, "16781", "16781_TR1_KVAR")
    matches = zenon_only_adms_match_rows(source, report.rows)
    assert matches
    assert any("16781 Q1 Q(kVar)" in row.values for row in matches)


def test_signal_detail_uses_right_side_implementation_summary_and_comment_navigation():
    root = _root()
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'QLabel("ADMS Implementation Summary")' in ui
    assert "db_smart_impl_list" in ui
    assert "_refresh_db_smart_implementation_summary" in ui
    assert "_db_smart_detail_cell_clicked" in ui
    assert "_locate_db_smart_implementation" in ui
    assert "_db_smart_implementation_highlight_keys" in ui
    assert 'QColor("#DCEEFF")' in ui
