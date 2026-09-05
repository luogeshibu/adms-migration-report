
from pathlib import Path

from migration_report_tool.config.column_schema import SOURCE_TYPES
from migration_report_tool.config.source_modules import MODULE_BY_KEY
from migration_report_tool.repository import SOURCE_DEFINITIONS, scan_repository
from migration_report_tool.version import __version__


def test_v08151_removes_zenon_xml_source_and_generation_contract(tmp_path):
    assert __version__ == "0.8.151"
    assert "zenon_xml" not in {item.key for item in SOURCE_DEFINITIONS}
    assert "zenon_xml" not in SOURCE_TYPES
    assert "zenon_xml" not in {item.source_type for item in MODULE_BY_KEY["rmu_review"].tables}

    package_root = Path(__file__).resolve().parents[1]
    assert not (package_root / "src/migration_report_tool/services/zenon_sld_service.py").exists()

    core_text = (package_root / "src/migration_report_tool/core.py").read_text(encoding="utf-8")
    ui_text = (package_root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    parser_text = (package_root / "src/migration_report_tool/infrastructure/parsers/legacy.py").read_text(encoding="utf-8")
    assert "parse_zenon_xml" not in core_text
    assert "write_zenon_sld_csv" not in core_text
    assert "Regenerate ZENON SLD" not in ui_text
    assert "def parse_zenon_xml" not in parser_text


def test_site_repository_ignores_xml_and_is_ready_with_six_tabular_sources(tmp_path):
    site = tmp_path / "1-ADF"
    site.mkdir()
    for name in (
        "SE.xlsx", "ZENON-SLD.csv", "ZENON-DB.csv",
        "ADMS-DB.csv", "ADMS-SLD.csv", "ZENON-ADMS-IOA.csv",
    ):
        (site / name).write_bytes(b"x")
    (site / "ADF.XML").write_text("<Subject/>", encoding="utf-8")

    info = scan_repository(tmp_path, deep=False)[0]
    assert info.ready
    assert sorted(info.sources) == [
        "adms_db", "adms_sld", "ioa", "se_list", "zenon_db", "zenon_sld"
    ]
    assert "ADF.XML" not in [path.name for path in info.unmapped_files]
