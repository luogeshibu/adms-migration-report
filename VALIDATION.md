## v0.8.20 validation additions

- Dashboard exception actions are intent-aware: RMU Issues applies `ANY MISMATCH`; Signal Mismatches applies `MISMATCHED`.
- Signal Mapping Review now has an explicit result filter for ALL RESULTS / MATCHED / MISMATCHED / UNCHECKED.
- Frozen RMU and Signal Review cells can be double-clicked to open the audited human Review state editor.
- Dashboard exception buttons disable themselves when the latest validation contains no corresponding exception.

## v0.8.19 validation additions

- Project Overview now calculates a real delivery state and renders the four-step Data Sources -> Validation -> Human Review -> Migration Report workflow.
- Global action label is `Run Validation`; the obsolete decorative `MIGRATION REVIEW` label is absent.
- RMU dashboard explicitly shows Pass / With Issues and Review progress; field counts are labeled as affected RMUs by field.
- Signal dashboard explicitly reconciles Total = Checked + Unchecked and Checked = Matched + Mismatched; match rate is Matched / Checked.
- RMU Review fingerprint regression: unrelated display/source values do not reset Review, while changed automatic Analysis resets Reviewed/Needs Action to Unreviewed and writes an Audit entry.
- Signal Review fingerprint regression: a changed report-level source hash does not reset an unchanged row; a changed row fingerprint resets only that reviewed row to Unreviewed.
- ZENON-ADMS IOA is required for formal repository readiness.
- `resources/icons/*.svg` is included by the PyInstaller specification with `PySide6.QtSvg`.
- Top-right delivery state renders as a non-clickable `STATUS · ...` label; Report Export distinguishes formal readiness from review-draft export and checks report freshness against current validation/review state.

## v0.8.18 validation additions

- RMU automated Analysis and manual Review are separate UI states and filters.
- Frozen RMU locator contains four columns: No., RMU, Analysis, Review.
- Dashboard exposes independent RMU and Signal Mapping KPI groups.
- RMU KPI semantics are Pass / With Issues; Signal Mapping semantics are Matched / Mismatched.
- Both review modules support explicit manual Set Review actions.
- RMU Excel export includes Review status before Analysis.

## v0.8.17 UI validation additions

- Product identity is NARI Saudi ADMS Migration Report.
- Sidebar and top bar expose Saudi ADMS project / migration-review context without changing business algorithms.
- Project Overview includes explicit Organization, Project, Workstream, Deliverable and Current Site context.
- Navigation and page descriptions use project-delivery terminology while existing page indexes and actions remain unchanged.

## v0.8.16 validation additions

- Global Display Name persistence is isolated from site ProjectStore databases.
- Two independent site stores resolve the same global Display Name.
- ZENON DB `rmu_type` built-in presentation default is verified as `Device`, while the canonical System Field remains `RMU Type` and source alias remains `DEVICE`.
- Reset/default persistence compares against the presentation default rather than the canonical label.
- Formal Excel review headers and Import Sources metadata use the same effective global Display Name.

## v0.8.15 validation additions

- Module dependency registry is regression-tested: RMU Data Review exposes six source tables and Signal Mapping Review exposes IOA + shared ADMS SLD + application STANDARD.
- ZENON XML → derived ZENON SLD relationship is explicit in the module source view.
- Repository UI contract test verifies duplicate local Refresh Sources / Run Comparison actions are absent.
- Repository UI contract test verifies Module Source tabs and application STANDARD mapping are present.
- Full automated suite: 85 passed.

## v0.8.14 validation additions

- `Regenerate ZENON SLD` parses the live site XML with the same site/SE-feeder isolation rules used by comparison.
- Replacement is staged to a temporary CSV in the site directory and committed with `os.replace`; parse/write failure or zero generated RMUs preserves the previous `ZENON-SLD.csv`.
- Source Mapping exposes editable Display Name separately from immutable System Field/Internal Key and mapped Actual Column.
- Site Display Names persist in SQLite `source_display_names` and produce audit records without modifying source CSV/XLSX headers.
- RMU Data Review and Signal Mapping Review use the same site Display Names in desktop headers and formal Excel export.
- Automated regression suite: 80 tests passed.
- Source compile validation passed. The container does not have PySide6 installed, so a live Qt launch/packaged UI self-test cannot be executed in this environment.

## v0.8.13 validation additions

- RMU summary is now a single compact line: Total / Shown / non-zero Analysis field mismatch counts.
- Zero-count NAME / FEEDER / SMART / TYPE / IP / LINK fields are omitted from the summary.
- No comparison or source-mapping business logic changed.

## v0.8.12 validation additions

- ADMS DB schema contains no SMART canonical field.
- A physical SMART column in ADMS DB is ignored rather than consumed.
- ADMS DB without SMART produces no optional-column warning for SMART.
- SMART analysis excludes ADMS DB and uses ADMS SLD as the ADMS-side SMART source.

## v0.8.11 validation additions

- RMU Data Review source group titles contain no `From` prefix.
- UI and Excel export share the same source-group captions: SE / ZENON DB / Driver Info / ZENON SLD XML / ADMS DB / ADMS Channel / ADMS SLD.
- Ordinary English field labels use Title Case while technical abbreviations and Analysis indicators remain uppercase.

# Migration Report Tool v0.7.0 Validation

Validation date: 2026-08-22


## Analysis consistency policy

- NAME / FEEDER / SMART / TYPE use one blank-ignoring consistency engine.
- 0 non-blank values -> blank; 1 non-blank value -> TRUE; 2+ -> TRUE only if all normalized values agree.
- FEEDER site-prefix and numeric zero-padding normalization covered by regression tests.
- SMART alias/SE equipment classification normalization covered by regression tests.
- ZENON DB DEVICE participates in cabinet TYPE comparison.

## Responsive UI policy

- Site Repository: draggable master/detail splitter; `Detected File` stretches, Status/Modified/Size stay bounded.
- Audit Log: `Reason` stretches; ID/RMU/reviewer/timestamp stay bounded; empty state is shown when there are no audit rows.
- Versions: `Description` stretches; empty state is shown when there are no saved versions.
- Comparison: fixed-width grouped DATA header is preserved with per-pixel horizontal scrolling; it is intentionally not stretched across 54 columns.
- Python syntax/compile validation for the PySide6 UI module: PASS. Final visual/DPI verification remains a Windows runtime check because the build environment here does not provide PySide6/Windows GUI rendering.

## Automated checks

- Python compileall: PASS
- Existing end-to-end comparison/report regression: PASS
- Official SE `FEEDER` mapping regression: PASS
- Re-import/latest-source regression: PASS
- zenOn XML `Picture/@ShortName -> Screen name` regression: PASS
- Site Repository canonical filename discovery: PASS
- Current ADF legacy filename discovery: PASS
- Combined XML filename discovery (`ABN-ABN2.XML`): PASS
- Combined XML discovery among multiple XMLs using exact site filename token: PASS
- XML-or-SLD preflight rule: PASS
- ABN vs ABN2 exact feeder-token isolation: PASS
- SE feeder suffix positive match: PASS
- Analysis all-blank / single-value / equal / mismatch rule regression: PASS
- Analysis FEEDER normalization regression: PASS
- Analysis SMART alias normalization regression: PASS
- Analysis zero-placeholder handling regression: PASS
- Analysis end-to-end multi-source consistency regression: PASS
- Automated unittest total: 21 passed
- Existing sample comparison: 1021 RMU rows processed

## Real combined XML regression

Input: user-provided `ABN-ABN2.XML`.

The same physical XML was parsed twice with different selected sites:

```text
Selected site ABN2 -> 348 unique logical RMUs, 31 feeders
Selected site ABN  -> 462 unique logical RMUs, 32 feeders
ABN feeder leakage into ABN2 result: 0
ABN2 feeder leakage into ABN result: 0
```

Records belonging to other feeder tokens in the combined export are excluded from both site runs.

## Windows build

The source package has one authoritative production build/release entry point: root `build.ps1`. The script runs regression tests, compiles the checked-in PyInstaller specification, executes the packaged `--self-test`, then creates the versioned application folder, ZIP, manifest and SHA256 files directly under `release\v<version>\`. Legacy BAT build/release wrappers and the formal `dist\` output path have been removed.


## v0.6.0 UI regression

- Shared EmptyState no longer relies on wrapped QLabel size hints while independently centered.
- Audit Log and Versions empty-state subtitles have explicit width and minimum height.
- Responsive table header/row sizes are standardized.

## v0.6.2 DB Smart Report regression
- Historical validation: legacy DB-smart worksheet support existed in older versions; v0.8.2 no longer uses it.
- Cached Type / Analysis values are preserved.
- Review status/comments persist to SQLite and generate shared audit entries.
- Comparison UI display order starts with Analysis / Remarks / Comments / No. / RMU.

## v0.6.4 table visual regression

- Comparison page exposes one `Run Comparison` action (global top bar); the duplicate page-local button is removed.
- Comparison grouped schema renders `Index -> No. / RMU`.
- DB Smart parser promotes blank worksheet row-1 cells above `RMU_NO / Type` into an explicit `RMU` group.
- Standard and grouped table headers use neutral hierarchy colors only.
- Comparison business colors remain limited to data rows and FALSE Analysis cells.
- Selected rows preserve status fills by using outline selection styling instead of blue fill.


## v0.6.4 unified export regression

- Formal export sheet order is exactly: RMU Data Review, Signal Mapping Review, STANDARD, Import Sources, Change Audit Log.
- Signal mapping source columns are preserved; Review and Comments are appended at the right edge.
- Signal-mapping formulas that referenced DATA are rewritten to the renamed RMU Data Review sheet.
- STANDARD remains available for signal-mapping formulas.
- Helper sheets are removed from the exported deliverable.


## v0.6.5 spreadsheet selection regression

- Review grids use `SelectItems` + `ExtendedSelection`.
- Forced row selection click handlers are removed.
- Ctrl/Shift multi-range selection is enabled by Qt's extended selection model.
- Empty grid clicks and clicks outside a review grid clear both selection and current index.
- Selection styling remains outline-only so business colors stay visible.

## v0.6.6 app-format export regression

- Formal export still contains exactly five sheets.
- `RMU Data Review` starts with `Analysis / Remarks / Comments / Index` exactly like the App review workspace.
- `Signal Mapping Review` starts with `Review / Comments / RMU` exactly like the App signal-review workspace.
- `DATA`, `DB-smart report`, `DB-smsrt report` and helper sheets are not used as delivery layouts.
- `STANDARD` is copied from the bundled `resources/templates/IOA STANDARD.xlsx`; site REPORT workbooks are ignored.
- App row status colors and FALSE-cell emphasis are reproduced in the generated RMU review worksheet.

## v0.6.7 severity-color regression

- Row colors depend only on issue severity: Pass / 1 Issue / 2 Issues / Critical.
- NAME=FALSE is always Critical; 3+ FALSE Analysis fields are Critical.
- FEEDER+TYPE and FEEDER+SMART both resolve to the same 2-Issue row severity rather than unique combination colors.
- FALSE-cell colors remain stable by field: NAME red, FEEDER yellow, SMART blue, TYPE orange.
- RMU Data Review Excel export uses the same shared status engine and embeds a color-rule explanation as Excel comments.
- Automated v0.6.7 test suite: 31 tests passed in the packaging environment.


## v0.6.8 frozen-row locator regression

- RMU Data Review renders a fixed No. / RMU / Status locator beside the wide source grid.
- Signal Mapping Review renders a fixed RMU / Type / Review locator.
- Vertical scroll values are synchronized between locator and main views.
- Hover and active-row tracking use border-only painting and therefore preserve business/status fills.
- Locator clicks activate the matching main row while preserving horizontal scroll.
- Main grids remain SelectItems + ExtendedSelection for Ctrl/Shift multi-range review.

- v0.6.8 automated source/regression suite: 27 tests passed.

## v0.7.0 IP/LINK + Signal Mapping calculation regression
- RMU Data Review Analysis schema contains NAME / FEEDER / SMART / TYPE / IP / LINK.
- IP compares Driver info `PRIMARY_IP` with ADMS Channel `NET_DESCRIPTION1` after IP normalization.
- LINK is evaluated from the selected RMU's ADMS-SLD association field; missing ADMS-SLD rows are N/A rather than false failures.
- IP/LINK FALSE cases retain exact field colors, detailed tooltips, and Remarks reasons.
- Signal Mapping Review rejects the legacy DB-smart worksheet as a source.
- Signal Mapping is calculated from IOA + ADMS SLD + STANDARD only.
- STANDARD parser reads only columns Type / IOA / name.
- `(RMU Type, ADMS_DOT_NO)` selects the STANDARD signal and ADMS/STANDARD analysis records an explicit reason.
- Formal export contains exactly five approved sheets.

## v0.7.3 Windows Excel handle validation

- `read_excel_rows()` closes read-only XLSX workbooks on normal completion.
- Empty worksheet return paths still close the workbook.
- Exceptions raised during row streaming still close the workbook.
- Formal report export closes the source workbook in `finally`.
- Self-test workbook inspection closes in `finally`.
- Linux/container regression result during packaging: 38 tests passed.


## v0.8.2 validation additions
- Bundled `resources/templates/IOA STANDARD.xlsx` is the only template workbook.
- Signal Mapping does not resolve a site REPORT workbook.
- ABH feeder normalization is independent of exact repository folder naming.

## v0.8.5 validation additions

- Windows bootstrap contract: root operational scripts are exactly `setup.bat` and `build.ps1`; `setup.ps1` is intentionally absent.
- `setup.bat` owns supported x64 Python discovery, `.venv` creation/recreation, locked dependency installation, editable package installation, `pip check`, import verification and application self-test.
- `build.ps1` never creates a venv and never installs packages; it validates the prepared environment and exact direct lock versions before release work begins.
- Formal build continues to use explicit `-PythonArgs`, preventing accidental interactive Python REPL startup.


## v0.8.6 validation additions

- `setup.bat` stores Python launcher executable and selector separately.
- Virtual environment creation goes through `:run_bootstrap`, so `py -3.14 -m venv` is preserved at execution time.
- Setup refuses to execute when the bootstrap executable is empty.


## v0.8.7 validation additions

- Current ABH sample-data set is the only content under `examples/sample-data`.
- Source Mapping Actual Column uses `NoWheelComboBox`; mouse wheel cannot change mapping.
- RMU review status is explicit SQLite state and is audited independently from manual data corrections.
- RMU summary tooltip documents automatic result counts versus manual review counts.


## v0.8.8 validation additions

- `ABN-12`, `JED-NTH-ABN-12`, and `ABN-AH312` normalize to logical feeder `12`.
- `ABN-1`, `ABN-01`, and `ABN-AH301` normalize to logical feeder `1`.
- SE Source Mapping has no duplicate `device` canonical key; `EQUIP. TYPE` maps to SMART/NORMAL.
- Source Mapping displays stable Internal Key and supports Reset All to Auto while mouse-wheel changes remain disabled.
- Active STANDARD precedence is User Override -> Built-in; both Signal Mapping Review and formal export use the same active path.
- Uploaded STANDARD is rejected unless the STANDARD sheet contains required named columns Type / IOA / name and at least one data row.

## v0.8.10 validation additions

- RMU Data Review now shows a dedicated two-line summary card below the filters.
- Summary explicitly explains how Analysis issues / Matched / Warning / Failed / Reviewed / Needs action / Unreviewed are counted.
- Summary also shows FALSE breakdown counts for NAME / FEEDER / SMART / TYPE / IP / LINK.
- Signal Mapping Review summary was moved out of the filter row into its own summary card for readability.
- Grouped review headers are slightly taller to reduce clipping on Windows DPI scaling.
- Signal Mapping Review column captions and widths were updated so ZENON DOT NO / ADMS DOT NO / STANDARD DOT NO remain fully visible.

## v0.8.9 validation additions

- UI terminology only: `Open Workspace`, `Select Workspace`, and `Workspace`.
- The underlying repository-root property, read-only source scanning, per-site application workspace, SQLite state, and comparison logic remain unchanged.
- Regression check confirms user-facing `Open Root` / `Change Root` labels are no longer present in `main_window.py`.
