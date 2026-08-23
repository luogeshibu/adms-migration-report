from pathlib import Path


def test_saudi_adms_project_ui_identity():
    root = Path(__file__).resolve().parents[1]
    schema = (root / "src/migration_report_tool/config/column_schema.py").read_text(encoding="utf-8")
    ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    launcher = (root / "src/migration_report_tool/app/application.py").read_text(encoding="utf-8")

    assert 'APP_NAME = "NARI Saudi ADMS Migration Report"' in schema
    assert 'QLabel("NARI")' in ui
    assert 'QLabel("SAUDI ADMS PROJECT")' in ui
    assert '("Project Overview", 0, "overview")' in ui
    assert '("Site Data Sources", 1, "database")' in ui
    assert '"Saudi ADMS Migration Overview"' in ui
    assert '"Migration Report Export"' in ui
    assert 'NARI.SaudiADMS.MigrationReport' in launcher
