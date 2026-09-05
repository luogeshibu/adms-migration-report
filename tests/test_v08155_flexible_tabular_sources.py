from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook

from migration_report_tool.config.column_schema import SOURCE_TYPES
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import _source_extensions, rank_source_candidates
from migration_report_tool.infrastructure.parsers import read_excel_raw, resolve_excel_sheet_name, list_excel_sheets, read_mapped_rows
from migration_report_tool.version import __version__


def _book(path: Path):
    wb = Workbook()
    cover = wb.active
    cover.title = "Cover"
    cover["A1"] = "Read me"
    data = wb.create_sheet("Equipment")
    data.append(["DeviceName", "DeviceScope", "SubType", "SMART", "DeviceType", "Picture"])
    data.append(["1001", "JED-CTL-ADF-16", "2L1T", "SMART", "RMU", "ADF110"])
    wb.save(path)


def test_release_version():
    assert __version__ == "0.8.155"


def test_all_site_sources_accept_csv_and_excel():
    for key in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld", "ioa"):
        assert {".csv", ".xlsx", ".xlsm"}.issubset(_source_extensions(key))
        filters = SOURCE_TYPES[key][1]
        text = " ".join(pattern for _label, pattern in filters)
        assert "*.csv" in text and "*.xlsx" in text


def test_excel_auto_uses_first_usable_sheet_and_manual_sheet_can_be_pinned():
    with TemporaryDirectory() as td:
        path = Path(td) / "anything-at-all.xlsx"
        _book(path)
        assert resolve_excel_sheet_name(path) == "Equipment"
        infos = list_excel_sheets(path)
        assert [i.name for i in infos] == ["Cover", "Equipment"]
        headers, rows = read_excel_raw(path)
        assert headers[0] == "DeviceName"
        assert rows[0]["DeviceName"] == "1001"
        headers_cover, _rows_cover = read_excel_raw(path, sheet_name="Cover")
        assert headers_cover == ["Read me"]


def test_arbitrary_excel_filename_maps_as_zenon_sld_by_fields():
    with TemporaryDirectory() as td:
        path = Path(td) / "customer_export_2026_final.xlsx"
        _book(path)
        ranked = rank_source_candidates(path)
        assert any(key == "zenon_sld" and score >= 75 for key, score, _detail in ranked)
        mapped = read_mapped_rows("zenon_sld", path)
        assert mapped.rows[0]["rmu"] == "1001"
        assert mapped.rows[0]["device_type"] == "RMU"


def test_sheet_selection_is_site_level_and_persistent():
    with TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "project")
        try:
            assert store.source_sheet_name("zenon_sld") == ""
            store.set_source_sheet_selection("zenon_sld", "Equipment", "tester")
            assert store.source_sheet_name("zenon_sld") == "Equipment"
            store.clear_source_sheet_selection("zenon_sld", "tester")
            assert store.source_sheet_name("zenon_sld") == ""
        finally:
            store.close()


def test_site_data_sources_ui_exposes_sheet_and_unrestricted_supported_browse():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert '"App Table", "Source File", "Sheet", "File Path"' in ui
    assert "choose_source_sheet_for_table" in ui
    assert "Supported tables (*.csv *.xlsx *.xlsm)" in ui
    assert "field mapping, not filename, defines the source role" in ui
