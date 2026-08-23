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
        # Structured Resolution replaces free-form RMU Comments. Pick one issue
        # row and resolve every FALSE field with the first available source;
        # LINK uses Accepted Exception because it is an association flag.
        issue_row = next(row for row in rows if any(str(row.get(f"analysis_{field.lower()}", "")).upper() == "FALSE" for field in ("NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK")))
        issue_rmu = issue_row["rmu"]
        for field in ("NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK"):
            if str(issue_row.get(f"analysis_{field.lower()}", "")).upper() != "FALSE":
                continue
            candidates = (issue_row.get("resolution_candidates") or {}).get(field, [])
            if field != "LINK" and candidates:
                candidate = candidates[0]
                store.set_rmu_resolution(
                    issue_rmu, field, "USE_SOURCE", "selftest",
                    selected_source=candidate.get("source", ""), selected_value=candidate.get("value", ""),
                    normalized_value=candidate.get("normalized", ""),
                    analysis_fingerprint=store._rmu_field_fingerprint(issue_row, field),
                )
            else:
                store.set_rmu_resolution(
                    issue_rmu, field, "ACCEPT_EXCEPTION", "selftest",
                    analysis_fingerprint=store._rmu_field_fingerprint(issue_row, field),
                )
        store.sync_rmu_review_from_resolutions(issue_rmu, issue_row, "selftest")
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
            assert ws["I1"].value == "Resolution"
            assert ws["J1"].value == "Index"
            assert ws["J2"].value == "No."
            assert ws["K2"].value == "RMU"
            assert ws["L1"].value == "SE"
            assert str(ws["K3"].value) == str(rows[0]["rmu"])
            # Structured issue decisions must be exported in the Resolution column.
            issue_excel_row = next(r for r in range(3, ws.max_row + 1) if str(ws.cell(r, 11).value or "") == str(issue_rmu))
            assert ws.cell(issue_excel_row, 9).value, "Resolution summary must be exported"
            assert ws.cell(issue_excel_row, 1).value == "REVIEWED"

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
