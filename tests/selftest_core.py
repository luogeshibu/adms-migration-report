"""Non-UI validation of comparison, SQLite, template-fill and export behavior."""
from pathlib import Path
import shutil

from openpyxl import load_workbook

from migration_report_tool.core import COLUMNS, ProjectStore, REPORT_MERGES, build_comparison, export_report, workspace_root


def run_selftest():
    mapping = {
        "se_list": "SE.xlsx",
        "zenon_db": "ZENON-DB.csv",
        "zenon_sld": "ZENON-SLD.csv",
        "adms_db": "ADMS-DB.csv",
        "adms_sld": "ADMS-SLD.csv",
        "ioa": "ZENON-ADMS-IOA.csv",
    }
    root = Path(__file__).resolve().parents[1] / "examples" / "sample-data"
    project = workspace_root() / "_SELFTEST_V080"
    if project.exists():
        shutil.rmtree(project)
    store = ProjectStore(project)
    try:
        for source, filename in mapping.items():
            store.set_source(source, root / filename)
        rows, summary = build_comparison(store)
        assert rows, "comparison returned no rows"
        assert len(COLUMNS) == 55, f"RMU review schema must contain 55 source/review columns, got {len(COLUMNS)}"
        assert "channel_analysis" not in rows[0], "obsolete ADMS Channel Analysis field must not be computed"
        store.save_comparison(rows)
        first_rmu = rows[0]["rmu"]
        store.update_value(first_rmu, "comments", "SE review: verify field mapping", "selftest", "SE user comment / modification advice")
        # A rerun must retain the manually reviewed comment through the audit override layer.
        rerun_rows, _ = build_comparison(store)
        store.save_comparison(rerun_rows)
        target = export_report(store)
        assert target.exists(), "Excel export not created"

        wb = load_workbook(target, read_only=False, data_only=False)
        try:
            expected_sheets = ["RMU Data Review", "Signal Mapping Review", "STANDARD", "Import Sources", "Change Audit Log"]
            assert wb.sheetnames == expected_sheets, f"unexpected export sheets: {wb.sheetnames}"

            # RMU Data Review must mirror the App review workspace, not the source DATA order.
            ws = wb["RMU Data Review"]
            assert ws["A1"].value == "Review"
            assert ws["A2"].value == "Review"
            assert ws["A3"].value == "UNREVIEWED"
            assert ws["B1"].value == "Analysis"
            assert [ws.cell(2, c).value for c in range(2, 8)] == ["NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK"]
            assert ws["H1"].value == "Remarks"
            assert ws["I1"].value == "Comments"
            assert ws["J1"].value == "Index"
            assert ws["J2"].value == "No."
            assert ws["K2"].value == "RMU"
            assert ws["L1"].value == "SE"
            assert str(ws["K3"].value) == str(rows[0]["rmu"])
            # The manually reviewed App comment must be exported in the App Comments column.
            assert ws["I3"].value == "SE review: verify field mapping"

            # Signal Mapping Review must also mirror the App model: Review first, then RMU/source groups.
            signal = wb["Signal Mapping Review"]
            assert signal["A1"].value == "Review"
            assert signal["A2"].value == "Review"
            assert signal["B2"].value == "Comments"
            assert signal["C1"].value == "RMU"
            assert signal["C2"].value == "RMU"
            assert signal["D2"].value == "Type"
            assert signal["E1"].value == "ZENON"
            assert signal["A3"].value == "UNREVIEWED"

            assert wb["STANDARD"].max_row > 1
            assert wb["Import Sources"]["A1"].value == "Source Type"
            assert wb["Change Audit Log"]["A1"].value == "ID"
            # STANDARD is copied from the bundled IOA STANDARD workbook; legacy DATA/DB-smart helpers are absent.
            assert "DATA" not in wb.sheetnames
            assert "DB-smsrt report" not in wb.sheetnames
            assert "DB-smart report" not in wb.sheetnames
        finally:
            wb.close()
        print(f"PASS: {len(rows)} rows; {summary}; export={target.name}")
    finally:
        store.db.close()
        shutil.rmtree(project, ignore_errors=True)


if __name__ == "__main__":
    run_selftest()
