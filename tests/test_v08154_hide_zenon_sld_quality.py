from pathlib import Path

from migration_report_tool.config.column_schema import (
    EQUIPMENT_INVENTORY_GROUPS,
    EQUIPMENT_SOURCE_GROUPS,
)
from migration_report_tool.version import __version__


def _keys(groups):
    return [key for _group, _color, columns in groups for key, _label, _width in columns]


def test_release_version():
    assert __version__ == "0.8.154"


def test_customer_facing_equipment_source_grid_has_no_quality_traceability_group():
    names = [name for name, _color, _columns in EQUIPMENT_SOURCE_GROUPS]
    assert names == ["Index", "Source Coverage", "SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"]
    keys = set(_keys(EQUIPMENT_SOURCE_GROUPS))
    hidden = {
        "equipment_quality",
        "eq_zsld_name_status",
        "eq_zsld_confidence",
        "eq_zsld_resolved_full_name",
        "eq_zsld_element_name",
        "eq_zsld_classification_reason",
        "eq_zsld_warning",
    }
    assert not (keys & hidden)


def test_legacy_inventory_layout_also_does_not_surface_quality_traceability():
    names = [name for name, _color, _columns in EQUIPMENT_INVENTORY_GROUPS]
    assert "Data Quality" not in names
    keys = set(_keys(EQUIPMENT_INVENTORY_GROUPS))
    for key in ("inventory_quality", "zsld_name_status", "zsld_confidence", "zsld_resolved_full_name", "zsld_element_name", "zsld_classification_reason", "zsld_warning"):
        assert key not in keys


def test_equipment_source_renderer_does_not_color_rows_by_extractor_quality():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    start = ui.index('if mode == "equipment_sources":')
    end = ui.index('        review_map = ctx["review_map"]', start)
    block = ui[start:end]
    assert "quality_fills" not in block
    assert 'data.get("equipment_quality")' not in block
    assert 'data.get("eq_zsld_warning")' not in block
    assert 'key == "equipment_source_count"' in block


def test_customer_facing_summary_does_not_publish_extractor_quality_counts():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    start = ui.index("def _background_rmu_render_prepare_job")
    end = ui.index("        emit(8, \"Reading cached RMU review rows\")", start)
    block = ui[start:end]
    assert "quality_text" not in block
    assert "No quality flags" not in block
    assert "OK / REVIEW / ATTENTION" not in block
