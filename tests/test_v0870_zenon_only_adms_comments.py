from pathlib import Path

from migration_report_tool.domain.mapping.signal_mapping import (
    build_signal_mapping_report,
    SIGNAL_MAPPING_COLUMNS,
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


def _row(report, rmu: str, zenon_name: str):
    index = {key: i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)}
    zenon_index = index["zenon_signal_name"]
    return next(
        row for row in report.rows
        if row.rmu == rmu and zenon_index < len(row.values) and row.values[zenon_index] == zenon_name
    )


def test_zenon_only_y1_kvar_comment_finds_adms_implementation_on_different_dot():
    report = _report()
    row = _row(report, "16781", "16781_Y1-16782_KVAR")
    assert signal_row_is_zenon_only(row)
    assert "16781 Y1 Q(kVar)" in row.suggested_comment
    assert "ADMS DOT 13059" in row.suggested_comment
    assert "Y1 + KVAR" in row.suggested_comment


def test_zenon_tr_channel_maps_to_adms_q_channel_for_comment_lookup():
    report = _report()
    row = _row(report, "16781", "16781_TR1_KVAR")
    assert signal_row_is_zenon_only(row)
    assert "16781 Q1 Q(kVar)" in row.suggested_comment
    assert "TR1→Q1 + KVAR" in row.suggested_comment


def test_zenon_only_comment_is_visible_and_exported_when_no_manual_comment_exists():
    root = _root()
    ui_source = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    export_source = (root / "src" / "migration_report_tool" / "infrastructure" / "export" / "workbook_exporter.py").read_text(encoding="utf-8")
    assert 'clean(review.get("comments")) or clean(getattr(row, "suggested_comment", ""))' in ui_source
    assert 'review.get("comments") or getattr(source_row, "suggested_comment", "")' in export_source


def test_action_remark_editor_starts_only_from_persisted_user_comment():
    source = (_root() / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'current_comment=clean(review.get("comments"))' in source
    assert 'clean(getattr(row, "suggested_comment", ""))' not in source[source.index("def edit_db_smart_cell"):source.index("def open_db_smart_source")]
