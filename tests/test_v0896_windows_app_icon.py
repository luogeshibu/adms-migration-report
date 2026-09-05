from pathlib import Path


def test_windows_icon_contract_uses_runtime_png_and_embedded_ico():
    root = Path(__file__).resolve().parents[1]
    app = (root / "src/migration_report_tool/app/application.py").read_text(encoding="utf-8")
    ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    spec = (root / "packaging/windows/MigrationReportTool.spec").read_text(encoding="utf-8")
    build = (root / "build.ps1").read_text(encoding="utf-8")
    version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

    assert '__version__ = "0.8.120"' in version
    assert '"NARI.SaudiADMS.MigrationReport"' in app
    assert 'for name in ("logo.png", "logo.ico")' in app
    assert 'window.setWindowIcon(icon)' in app
    assert 'WM_SETICON = 0x0080' in app
    assert 'LoadImageW.restype = ctypes.c_void_p' in app
    assert 'ICON_SMALL' in app and 'ICON_BIG' in app
    assert 'resource_root() / "assets" / "logo.png"' in ui
    assert 'icon=str(RES / "assets" / "logo.ico")' in spec
    assert 'verify_windows_icon.py' in build
    assert (root / "resources/assets/logo.png").is_file()
    assert (root / "resources/assets/logo.ico").is_file()
