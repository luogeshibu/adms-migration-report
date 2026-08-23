## v0.8.33 - Preserve Review Grid Viewport After Edits

- Fixed RMU Data Review horizontally jumping toward the Index/source columns after saving a structured Resolution or optional manual Review comment.
- RMU reselection now locates the row using the protected RMU key but keeps the active cell inside the user's current visible viewport.
- Horizontal scroll position is restored synchronously and on the next Qt event-loop turn to prevent deferred ensure-visible scrolling.
- Resolution, manual Review comment, optional Pass Review and audited value-edit refresh paths all inherit the same viewport-preserving behavior.
- Added a regression contract preventing `PositionAtCenter` reselection of the far-right RMU key column.

## v0.8.32 - Public README Cleanup

- Removed company and country/project branding from the public README title.
- README now uses the generic public repository name `ADMS Migration Report Tool`.
- Application UI/project identity is unchanged.

## v0.8.31 - Business-Facing Change Audit

- Added a Module column to Change Audit so RMU Data Review, Signal Mapping Review, Site Data Sources and Display Name actions are immediately distinguishable.
- Replaced internal audit field keys in the UI/export with business-facing Field labels while preserving immutable raw keys in SQLite.
- Field tooltips expose the original internal key for technical traceability.
- Normalized audit Record labels such as `DBSMART:5839` to `RMU 5839`.
- Updated the exported Change Audit Log sheet to match the application business view.

## v0.8.30 - Optional RMU Review Comments in Resolution


- Added an audited `manual_comment` field to RMU human Review state.
- Pass RMUs still default to `Not Required`, but the Resolution column can now be double-clicked to record an optional human Review comment.
- When a single Pass RMU is manually marked Reviewed or Needs Action, the App immediately offers the Review Comment editor.
- Issue RMUs continue to use structured per-FALSE Resolution decisions; optional Pass comments never replace or bypass issue Resolution.
- RMU search now includes the optional manual Review comment.
- Formal Excel export writes optional Pass human-review comments into the Resolution column.
- Manual Review comments are preserved independently of the automatic Analysis result and are audited as `rmu_review_comment`.

## v0.8.29 - Optional RMU Pass Review Parity

- RMU Data Review now matches Signal Mapping Review: automatic Pass rows default to `Not Required` but are no longer locked.
- Pass RMUs can be explicitly marked `Reviewed` or `Needs Action`, or reset to the default `Not Required` state.
- Issue RMUs still require structured per-FALSE-field Resolution and cannot bypass Resolution by manually marking Reviewed.
- Rows without a complete automatic Analysis remain `Validation Required` and cannot be manually overridden.
- Optional Pass reviews do not inflate the required Human Review denominator; optional `Needs Action` still blocks formal export.
- RMU Review filters now include `NOT REQUIRED` and `VALIDATION REQUIRED`.
- Excel export preserves explicit optional RMU Reviewed / Needs Action states.

## v0.8.28 - Optional Manual Review and Neutral Comments

- Signal Mapping Comments cells now always render with a plain white background in the App and formal Excel export; comments are annotation-only and never inherit validation/review colors.
- Matched signals still default to `Not Required`, but are no longer locked: reviewers can explicitly mark them `Reviewed` or `Needs Action` when a manual check is useful.
- `Default / Clear Manual Review` returns a matched row to `Not Required` and a mismatch row to `Unreviewed`.
- Unchecked rows remain `Validation Required`; review status cannot override incomplete validation, while Comments can still be recorded.
- Required Human Review progress still counts mismatches only. Optional `Needs Action` on a matched signal is nevertheless treated as an actionable condition and blocks formal export.
- App and Excel now share one signal review display-status function to prevent status drift between UI and exported reports.

## v0.8.27 - Signal Locator Lockstep Synchronization

- Fixed Signal Mapping Review frozen Row Locator drifting away from the main grid during vertical scrolling.
- Signal locator now uses the same `ScrollPerPixel` mode as the main grid, so synchronized scrollbar values use the same coordinate system.
- Locator RMU and Type are now rendered directly from the same `row.values` used by the main RMU group, eliminating a second presentation identity path.
- Fixed Signal Mapping row painting so each visible row carries its own automatic analysis result instead of reusing a stale loop value.
- RMU Data Review locator behavior was rechecked and already used matching pixel-scroll modes.

## v0.8.26 - Review Visual Separation and Table Readability

- Reserved green Review status exclusively for human-reviewed exceptions.
- Replaced automatic `Auto Validated` Review text with neutral `Not Required` for RMU pass rows and matched Signal Mapping rows.
- Added a unified Human Review palette: Not Required (blue-gray), Unreviewed (neutral), Reviewed (green), Needs Action (red), Validation Required (amber).
- Separated Signal Mapping automatic row tint from Human Review status color so Matched and Reviewed can no longer be confused.
- Widened frozen Signal Mapping Review status columns to prevent status text clipping.
- Updated formal Excel export to use the same automatic-analysis vs Human Review color semantics as the desktop App.

## v0.8.25 - Exception-Based Human Review and Validation Coverage

- Human Review progress now counts only actionable exceptions: one item per active RMU FALSE field plus one item per Signal Mapping mismatch.
- Pass RMUs and Matched signals are shown as `Auto Validated` and no longer inflate the Human Review denominator.
- Signal `Unchecked` rows are treated as Validation Coverage gaps, not Human Review items. Any unchecked signal blocks formal `READY FOR EXPORT`.
- Added delivery state `VALIDATION INCOMPLETE · N UNCHECKED`.
- Dashboard RMU Review now reports Resolved Issues / total RMU issue decisions; Signal Review reports processed mismatch decisions / total mismatches.
- Workflow Human Review percentage is calculated from exception decisions only. Zero exceptions means Human Review is already complete once Validation Coverage is complete.
- RMU `Set Review` action is replaced by `Resolve Issues`; pass rows require no manual review.
- Signal Human Review can be applied only to MISMATCHED rows; Matched is Auto Validated and Unchecked must be corrected/revalidated.
- RMU Resolution changes now participate in report freshness checks.

## v0.8.24 - Windows Formal Build Regression Fix

- Fixed Windows `WinError 32` during regression cleanup by explicitly closing every application-global `global_settings.db` SQLite connection.
- Formal end-to-end self-test now uses an isolated temporary application-global settings root and never depends on or modifies the operator's saved global Display Name overrides.
- Prevents legitimate workstation Display Name customizations from changing deterministic Excel header assertions during release builds.
- No RMU comparison, Signal Mapping, Resolution, Review, feeder normalization or report business rules were changed.

## v0.8.23 - Simplified Analysis Colors and Live Review Status

- Simplified RMU Analysis colors to three row meanings only: Pass, Has Issues, and Critical.
- One-issue and two-issue rows now share the same pale-yellow issue color; their labels still show the exact issue count.
- All FALSE Analysis cells now use one shared pale-red mismatch highlight; the column header identifies NAME / FEEDER / SMART / TYPE / IP / LINK.
- Simplified the RMU legend to Pass / Has Issues / Critical / FALSE = mismatch.
- Replaced the long RMU workflow paragraph with live Review and Resolution progress: reviewed/processed RMUs, percentage, resolved issue decisions, total active issues, and Needs Action count.
- The top-right project status is now the live workflow stage rather than the last technical milestone. After validation it shows REVIEW PENDING with the combined RMU + Signal review percentage until all review items are complete.
- ACTION REQUIRED includes the live Needs Action count; READY FOR EXPORT appears only when all RMU and Signal review items are processed and no Needs Action remains.
- Validation remains a completed workflow step after Run Validation, but `VALIDATION COMPLETE` is no longer used as the overall delivery status.
- Excel RMU review colors and embedded color explanations now match the simplified App color system.

## v0.8.22 - Structured RMU Resolution Workflow

- Replaced free-form RMU `Comments` with a read-only **Resolution** summary.
- Every FALSE RMU Analysis field now creates one independent Resolution decision row: N errors require N decisions.
- Double-click a FALSE Analysis cell or the Resolution column to open the structured Resolution dialog.
- Cross-source issues (NAME / FEEDER / SMART / TYPE / IP) allow the reviewer to select the authoritative source/value from the latest Validation.
- LINK uses explicit action decisions because it is an ADMS-SLD association state rather than a cross-source value.
- Supported decisions: `Use <Source>`, `Needs Action`, and `Accept Exception`; `Unresolved` clears an existing decision.
- RMU Review is now derived from Resolution completeness: any unresolved issue -> Unreviewed; any Needs Action -> Needs Action; otherwise all active issues resolved -> Reviewed.
- Changed source values automatically invalidate only the affected Resolution decision and return the RMU to Unreviewed while preserving Audit history.
- Structured Resolution decisions are stored in SQLite, included in version snapshots, shown in Audit Log, and exported in the formal RMU Data Review workbook.
- Pass RMUs remain manually reviewable; issue RMUs cannot be bulk-marked Reviewed without per-error decisions.
- Added regression tests for per-error decision count, automatic Review derivation, Needs Action behavior, and selective invalidation after re-validation.

## v0.8.21 - Station-Aware Feeder Consistency

- FEEDER Analysis now compares the complete logical feeder identity: station/site token + feeder number.
- Region/routing prefixes such as `JED-NTH` remain ignored, so `ABH-22` and `JED-NTH-ABH-22` are equivalent.
- Same-number feeders from different stations are now correctly different: `ABH-22` != `ABN-22`.
- ADMS `AH3xx` feeder encoding continues to be decoded while retaining the station token, e.g. `JED-NTH-ABH-AH322` -> `ABH-22`.
- Numeric-only feeder values use the selected repository site's station token as a fallback identity.
- FEEDER tooltips now state the station-aware rule explicitly and display station-aware normalized values.
- Added regression coverage for cross-station same-number feeder mismatches.

## v0.8.20 - Actionable Review Navigation

- RMU frozen Review cells can now be double-clicked to change the human Review state directly; the existing Set Review button remains available for multi-row review.
- Signal Mapping frozen Review cells support the same direct double-click Review workflow.
- Added a dedicated Signal Mapping result filter: All Results / Matched / Mismatched / Unchecked.
- Project Overview `Review RMU Issues` now opens RMU Data Review with `ANY MISMATCH` applied instead of merely navigating to the page.
- Project Overview `Review Signal Mismatches` now opens Signal Mapping Review with `MISMATCHED` applied.
- Dashboard review-action buttons now show the current exception count and are disabled when there is nothing to review.
- When no RMU issues exist, the dashboard action reads `No RMU Issues`; when no signal mismatches exist, it reads `No Signal Mismatches`. Full module access remains available from the left navigation.

## v0.8.19 - Formal Delivery Workflow and Project Icons

- Removed the decorative `MIGRATION REVIEW` top-bar tag and replaced it with a real calculated project state: Sources Incomplete / Ready for Validation / Validation Complete / Review In Progress / Action Required / Ready for Export.
- Renamed the primary global action from `Run Comparison` to `Run Validation`; one validation run now reports both RMU and Signal Mapping results.
- Added a four-step Migration Workflow to Project Overview: Data Sources -> Validation -> Human Review -> Migration Report.
- Redesigned RMU dashboard KPIs with Total RMUs / Pass / With Issues / Reviewed / Needs Action and a dedicated Review progress bar.
- Renamed RMU issue summary to `Affected RMUs by field` so overlapping FEEDER / SMART / TYPE / IP / LINK counts are not mistaken for additive totals.
- Redesigned Signal Mapping KPIs with Total Signals / Checked / Matched / Mismatched / Unchecked / Needs Action, plus explicit `Matched / Checked` match-rate semantics.
- Added Signal and RMU Review progress bars; `Needs Action` counts as processed Review work but still blocks Ready for Export.
- Added formal Review guidance directly on both review pages. `Reviewed` means verified/accepted; `Needs Action` means correction required.
- Added automatic Review invalidation: an RMU returns to Unreviewed only when its automatic Analysis fingerprint changes; a Signal row returns to Unreviewed only when that row's validation fingerprint changes. Comments and Audit history are preserved.
- Made ZENON-ADMS IOA required for formal site readiness because Signal Mapping Review is part of the delivery workflow.
- Added packaged SVG icons for Project Overview, Site Data Sources, RMU, Signal Mapping, Audit, Versions, Report Export and Settings.
- Added RMU and Signal module icons on the Project Overview and source icons in the active-source list.
- Updated Windows release metadata to `NARI Saudi ADMS Migration Report` and added SVG icon assets / QtSvg to the PyInstaller release contract.
- The top-right state is explicitly labeled `STATUS · ...` so it cannot be mistaken for an action button.
- Report Export now shows delivery readiness and asks for confirmation when exporting an incomplete review as a draft; formal readiness requires completed Review with no Needs Action.
- Export freshness is compared against validation/review timestamps so an older workbook is not shown as the current completed Report step after new validation or Review changes.

## v0.8.18 - Analysis and Review Workflow Dashboard

- Split RMU automated Analysis from manual Review in the frozen Row Locator.
- RMU locator now shows No. / RMU / Analysis / Review as four independent columns.
- Replaced the mixed RMU status filter with a dedicated Review filter; Analysis keeps its own filter.
- Renamed Review Status action to Set Review.
- Added an explicit Set Review action to Signal Mapping Review for selected signal rows.
- Redesigned Project Overview with separate RMU Data Review and Signal Mapping Review KPI sections.
- RMU KPIs now use Total RMUs / Pass / With Issues / Reviewed / Needs Action plus direct field mismatch counts.
- Signal KPIs now use Total Signals / Matched / Mismatched / Reviewed / Needs Action plus checked count and match rate.
- Removed legacy Matched / Warnings / Failed presentation from the RMU workflow and Run Comparison completion dialog.
- Formal RMU Data Review Excel export now includes the manual Review status as a dedicated first group, matching the App workflow.

## v0.8.17 - NARI Saudi ADMS Project UI

- Repositioned the desktop UI as the NARI Saudi ADMS Project migration-report application instead of a generic CSV/report utility.
- Updated application/window identity to `NARI Saudi ADMS Migration Report`.
- Redesigned sidebar branding to show NARI, Saudi ADMS Project and Migration Report release identity.
- Added a project identity kicker and Migration Review tag to the global top bar.
- Renamed navigation to project-delivery language: Project Overview, Site Data Sources, Change Audit, Review Versions and Report Export.
- Added a project context banner to the overview showing Organization / Project / Workstream / Deliverable / Current Site.
- Updated dashboard, repository, audit, version, export and settings descriptions for the Saudi ADMS data-migration workflow.
- Formal workbook comments now identify the NARI Saudi ADMS Migration Report tool.
- No RMU comparison, signal-mapping, source-schema, XML parsing, SQLite or export-data algorithms were changed.

## v0.8.16 - Global Display Names and Header Truth

- Changed source Display Names from site-local project.db metadata to application-global settings stored under the persistent user-data root.
- One Display Name change now applies to every site, RMU Data Review, Signal Mapping Review and formal Excel exports.
- Actual Column overrides remain site-specific because physical source headers may differ between sites.
- Source Mapping now clearly separates System Field, Global Display Name and Actual Column (Current Site).
- Built-in Display Name defaults are derived from the real App review headers instead of the canonical business label.
- Fixed the confusing ZENON DB example where System Field `RMU Type` mapped to source column `DEVICE` while the App header displayed `Device`; the dialog now shows `Device` as the built-in Global Display Name.
- Reset Global Names restores the real built-in App header, not the canonical System Field label.
- Import Sources export now reports the same effective Display Name that the App/Excel review sheets actually use.
- Application-global display settings persist across release-folder replacement.

## v0.8.15 - Module Source Mapping Redesign

- Redesigned Site Repository around business modules instead of one flat source-file list.
- RMU Data Review now explicitly shows SE Equipment, ZENON XML, derived ZENON SLD, ZENON DB, ADMS DB and ADMS SLD as its source tables.
- Signal Mapping Review now explicitly shows ZENON-ADMS IOA, shared ADMS SLD and the active application IOA STANDARD reference.
- Shared physical tables intentionally appear in every module that consumes them, making module dependencies visible.
- IOA STANDARD now participates in the same Source Mapping / Display Name workflow as site tables; its active Built-in/User Override origin is visible.
- Signal Mapping Review and formal export now honor STANDARD column overrides and STANDARD Display Names saved for the active site workspace.
- Removed duplicate Site Repository actions: the global top bar keeps Refresh Sources / Run Comparison, while the repository page keeps only Workspace and site-specific actions.
- Removed duplicate local Run Comparison and local Refresh Sources buttons.
- Renamed the mapping action to Edit Selected Table Mapping; double-clicking a tabular source row opens the same mapping editor.

## v0.8.14 - ZENON SLD Regeneration and Site Display Names

- Added **Regenerate ZENON SLD** to Site Repository. It reuses the existing zenOn XML parser, applies the current site/SE-feeder isolation rules, writes a temporary CSV beside the target, and atomically replaces `<site>/ZENON-SLD.csv` only after a successful non-empty parse.
- A failed or zero-row XML parse leaves the existing `ZENON-SLD.csv` unchanged. The repository is automatically rescanned after a successful regeneration.
- Clarified the source model: ZENON XML is the graphical source of truth; `ZENON-SLD.csv` is a derived/fallback file.
- Added editable **Display Name** to Source Mapping while keeping System Field, Internal Key and Actual Column contracts unchanged.
- Display Names are site-local presentation metadata stored in the site's `project.db`, audited in Change Audit Log, and included in version snapshots.
- Site Display Names are applied to RMU Data Review, Signal Mapping Review, column-visibility dialogs and formal Excel review headers.
- Import Sources export now records System Field, Display Name and Actual Column separately.
- Added regression coverage for display-name persistence/application, atomic ZENON-SLD replacement, and zero-row protection.

## v0.8.12 - ADMS DB SMART Source Correction

## v0.8.13 - Simple RMU Issue Summary

- Simplified the RMU Data Review summary to show only Total, Shown, and per-field Analysis mismatch counts.
- Removed the verbose Analysis issues / Matched / Warning / Failed / Reviewed / Needs action / Unreviewed explanation from the summary card.
- Zero-count Analysis fields are hidden automatically, so a typical summary reads: `Total 238 · Shown 238 · FEEDER 10 · TYPE 6 · LINK 30`.
- Issue counts remain based on FALSE values in NAME / FEEDER / SMART / TYPE / IP / LINK and do not change comparison business logic.

- Removed the incorrect optional SMART field from the ADMS DB source schema.
- ADMS DB Source Mapping no longer shows a SMART row and no longer reports a warning merely because SMART is absent.
- SMART consistency analysis no longer includes ADMS DB.
- On the ADMS side, SMART is sourced from ADMS SLD only.
- Existing SE / ZENON SMART inputs remain unchanged.
- Added regression tests proving ADMS DB does not define or consume SMART.

## v0.8.11 - Review Header Naming Cleanup

- Removed `From` from RMU Data Review source group titles: `From SE` -> `SE`, `From ADMS DB` -> `ADMS DB`, and `From ADMS SLD` -> `ADMS SLD`.
- Standardized visible group naming to `Driver Info` while preserving technical acronyms such as SE, ZENON, ADMS, DB, SLD, XML, RMU, IP, SMART and LINK in uppercase.
- Standardized ordinary field captions to Title Case where appropriate: `Brand`, `Device`, `Screen Name`, and source-side `Type`.
- Analysis field names remain uppercase (`NAME / FEEDER / SMART / TYPE / IP / LINK`) because they are compact validation indicators rather than ordinary column captions.
- Exported Excel review headers use the same cleaned naming as the desktop UI.

# Changelog


## v0.8.10 - Review Summary Clarity and Signal Header Readability

- Moved RMU Data Review summary into a dedicated summary card below the filter bar.
- Added a second explanatory line so users can see exactly how Analysis issues / Matched / Warning / Failed / Reviewed / Needs action / Unreviewed are counted.
- Added visible FALSE-field breakdown counts for NAME / FEEDER / SMART / TYPE / IP / LINK.
- Added Unreviewed count to RMU Data Review summary.
- Widened Signal Mapping Review summary area and moved it into its own summary card.
- Increased grouped-header height for better readability on wide review tables.
- Renamed and widened Signal Mapping Review headers such as ZENON DOT NO / ADMS DOT NO / STANDARD DOT NO so header text is no longer clipped.

## v0.8.9 - Workspace UI Terminology

- Renamed **Open Root** to **Open Workspace**.
- Renamed **Change Root** to **Select Workspace**.
- Renamed the visible **Repository Root** field label to **Workspace**.
- Updated the folder picker title and validation message to use Workspace terminology.
- No repository scanning, site discovery, SQLite, comparison, feeder mapping, standard-reference, report, or source-snapshot business logic was changed.

## v0.8.8 - Feeder Suffix, Canonical Mapping & STANDARD Management

- FEEDER Analysis now compares the decoded logical feeder number: `ABN-12`, `JED-NTH-ABN-12`, and `ABN-AH312` all normalize to `12`; `ABN-1`, `ABN-01`, and `ABN-AH301` normalize to `1`.
- FEEDER normalization no longer depends on the Site Repository folder name and ignores presentation prefixes such as `JED-NTH`.
- FEEDER tooltips now show the original source value and its normalized comparison value.
- SE Source Mapping now mirrors the business model: Station / Feeder / RMU / SMART-NORMAL / OH-UG / RMU Type. The ambiguous duplicate Device mapping was removed.
- Source Mapping now shows the stable Internal Key beside the display label, supports explicit Site Override selection, Reset All to Auto, and still blocks mouse-wheel changes.
- Added application-wide STANDARD management. A validated uploaded workbook can replace the active `IOA STANDARD.xlsx` without becoming a Site Repository source.
- User STANDARD overrides are stored outside the release resources (LOCALAPPDATA on Windows), survive release-folder replacement, and can be reverted to the bundled default.
- Signal Mapping Review and formal export always use the same active STANDARD reference.

## v0.8.7 - Review Workflow & Current Sample Data

- Replaced `examples/sample-data` with the current ABH source set supplied by the user.
- Added explicit RMU review states: UNREVIEWED / REVIEWED / NEEDS ACTION.
- `Reviewed` is no longer inferred from any arbitrary Audit Log edit.
- Added Review Status action for one or multiple selected RMU rows.
- Disabled mouse-wheel selection changes in Source Mapping Actual Column combo boxes.
- Added explanatory summary tooltips for Analysis issues / Matched / Warning / Failed / Reviewed.

## v0.8.6 - Windows Setup Launcher Fix

- Fixed `setup.bat` virtual-environment creation when Python is selected through `py -3.14` or `py -3`.
- Split the bootstrap launcher into executable and selector components instead of storing `py -3.14` as one command string.
- Avoided CMD parenthesized-block early variable expansion by executing bootstrap Python through a dedicated `:run_bootstrap` subroutine.
- Added a guard that fails explicitly if the bootstrap executable is unexpectedly empty.

## v0.8.5 - Windows Bootstrap Simplification

- Removed `setup.ps1`; Windows environment initialization is now owned entirely by `setup.bat`.
- Repository operational scripts are fixed to exactly two entry points: `setup.bat` for environment bootstrap and `build.ps1` for formal release.
- `setup.bat` supports normal setup, `--recreate`, and `--verify` without requiring PowerShell execution-policy changes.
- `build.ps1` no longer creates a venv or installs dependencies. It fails fast with `Run setup.bat first` when the environment is missing or stale.
- Added exact installed-version verification against `requirements.lock.txt` before formal builds.
- Preserved v0.8.2/v0.8.4 business behavior: bundled IOA STANDARD reference, ABH feeder normalization, schema mapping, RMU/Signal Mapping review and five-sheet export.

## v0.8.4 - Developer Bootstrap Separation

- Added `setup.ps1` as the canonical developer environment bootstrap.
- Added one Windows convenience wrapper, `setup.bat`, which invokes `setup.ps1` with process-local ExecutionPolicy Bypass.
- `build.ps1` now reuses `setup.ps1` instead of duplicating Python discovery, venv creation and pip installation.
- Kept `build.ps1` as the only formal release entry point; legacy build/release/start/install BAT files remain removed.
- Added environment verification and `-ForceRecreateVenv` / `-VerifyOnly` setup options.

## v0.8.2 - Built-in STANDARD Reference + Feeder Normalization Fix

- `resources/templates` now contains only `IOA STANDARD.xlsx`.
- Signal Mapping Review no longer reads any REPORT workbook from Site Repository.
- STANDARD lookup is always `Type + IOA -> name` from the bundled reference workbook.
- Formal export copies the bundled STANDARD worksheet into the five-sheet delivery workbook.
- Site Repository no longer discovers or displays REPORT.xlsx as an input source.
- ABH feeder normalization now self-detects the confirmed ABH token when repository site labels differ, so `ABH-03`, `JED-NTH-ABH-3`, and `JED-NTH-ABH-AH303` compare equal.
- ADMS Channel remains IP/PORT only; the obsolete nested Analysis column is not restored.

## v0.8.1

- Added confirmed ABH feeder normalization: `ABH-03`, `ABH-3`, `JED-NTH-ABH-3`, and `JED-NTH-ABH-AH303` resolve to the same logical feeder; `AH308` resolves to feeder 08.
- Kept unknown feeder encodings conservative so genuine mismatches remain visible.
- Removed the obsolete `ADMS Channel / Analysis` source column and its calculation. Main Analysis `IP` remains the authoritative Driver-info vs ADMS-Channel check.
- Added regression coverage for ABH feeder aliases and the removed channel-analysis column.

## v0.8.0 — Architecture Baseline & Source Schema Mapping

- Reorganized implementation into app/domain/services/infrastructure/config/ui/utils layers.
- Added one formal `build.ps1` pipeline and one `requirements.lock.txt`; removed BAT wrappers and duplicate requirement files.
- Added canonical SourceSchema mapping for all tabular inputs with explicit aliases, required/optional validation, site overrides and audit history.
- Added Site Repository Schema status and Source Mapping dialog.
- RMU and Signal Mapping engines now consume canonical field names instead of external CSV headers.
- Import Sources export now records canonical field, actual column and mapping type.
- Validated current ZENON DB contract including DEVICE -> RMU Type and PRIMARY_IP/PRIMARY_PORT driver mapping.
- Preserved RMU Data Review, Signal Mapping Review, IP/LINK Analysis, frozen locators, multi-selection, color severity and five-sheet formal export.

## v0.7.3 - Single PowerShell Release Pipeline

- Replaced the fragmented build/release entry points with one root `build.ps1`.
- Removed `build.bat`, `build_exe.bat`, `build_release.bat`, `release.bat`, `scripts/build.ps1`, and `scripts/release.ps1`.
- `build.ps1` now performs environment validation, locked dependency enforcement, regression tests, PyInstaller compilation, packaged EXE self-test, release packaging, manifest creation and SHA256 generation in one run.
- Formal artifacts are generated only under `release/v<version>/`; the legacy `dist/` handover path is no longer used.
- Added an explicit running-application guard and clearer Windows file-lock cleanup diagnostics.
- Keeps the v0.7.2 deterministic Excel workbook-close fix and all v0.7.x RMU/Signal Mapping behavior unchanged.

## v0.7.2 - Windows Excel Handle Safety

- Fixed `WinError 32` during regression-test temporary-directory cleanup on Windows.
- `read_excel_rows()` now closes `openpyxl` read-only workbooks in a `finally` block on every exit path.
- Hardened workbook lifecycle in export/self-test paths so exceptions cannot strand XLSX handles.
- Added regression coverage that verifies workbook closure for normal, empty and exceptional Excel-read paths.
- Keeps all v0.7.1 IP/LINK Analysis, column migration, frozen locator and calculated Signal Mapping behavior unchanged.

## v0.7.1 - Analysis Column Migration Fix

- Fixes upgraded installations where saved v0.6.x column visibility settings hid the new IP and LINK Analysis columns.
- Adds a versioned comparison-column layout migration so new columns are auto-enabled exactly once without overwriting future user choices.
- Keeps IP/LINK filtering, tooltips, severity counting, Remarks, Columns dialog and Excel export aligned with the six-field Analysis model.

## 0.7.0
- Added RMU Data Review `IP` Analysis: Driver info IP vs ADMS Channel IP using normalized IP comparison.
- Added RMU Data Review `LINK` Analysis: authoritative association state from ADMS-SLD `LINK` (with compatible legacy aliases).
- Added detailed tooltips and Remarks for IP mismatches and unlinked RMUs; existing reason-analysis prompts are retained.
- Extended severity coloring to six Analysis fields without creating combination-specific row colors; IP FALSE is violet and LINK FALSE is rose.
- Rebuilt Signal Mapping Review as a calculation engine. It no longer reads `DB-smart report` / `DB-smsrt report`.
- Signal Mapping input is `ZENON-ADMS-IOA.csv`; RMU cabinet Type comes from `ADMS-SLD.csv`.
- The report workbook is now a STANDARD reference only. Signal Mapping reads only `STANDARD` columns `Type`, `IOA`, and `name`.
- STANDARD signal lookup uses `(RMU Type, ADMS_DOT_NO)` and produces explicit TRUE/FALSE diagnostic reasons.
- Formal export remains App-owned: `RMU Data Review`, `Signal Mapping Review`, `STANDARD`, `Import Sources`, `Change Audit Log`.

## 0.6.8

- Added a frozen `No. / RMU / Status` row locator to RMU Data Review.
- Added a frozen `RMU / Type / Review` row locator to Signal Mapping Review.
- Locator and main tables share synchronized vertical scrolling so row identity cannot drift while moving horizontally.
- Added hover-row guide lines and persistent active-row guide lines that do not overwrite business/status background colors.
- Clicking a locator row activates the same main-grid row without resetting the horizontal scroll position.
- Preserved Excel-style Ctrl/Shift multi-range selection in the main review grids.

## 0.6.7

- Replaced combination-specific RMU row colors with severity-based row status colors.
- Row status is now: Pass (green), 1 Issue (yellow), 2 Issues (orange), Critical / NAME (red).
- NAME=FALSE is always Critical; three or more Analysis mismatches are also Critical.
- Analysis FALSE cells keep stable field colors: NAME red, FEEDER yellow, SMART blue, TYPE orange.
- Removed the special FEEDER+TYPE purple row color and added issue-count / Critical filters.
- Updated the on-screen legend and RMU Data Review Excel export to explain the same color contract.

## 0.6.6

- Formal Excel export now mirrors the **App review layouts**, not the source DATA / DB-smart worksheet layouts.
- `RMU Data Review` is generated in App order: Analysis, Remarks, Comments, Index, then source-data groups.
- `Signal Mapping Review` is generated from the App signal-review model with Review/Comments first, followed by RMU, ZENON, ADMS, STANDARD I/O, Analysis and Comparison Summary.
- App neutral grouped headers, row status colors and FALSE-cell emphasis are reproduced in the generated review worksheets.
- `STANDARD` is the only worksheet preserved directly from the site's source REPORT workbook.
- Formal delivery still contains exactly five sheets: RMU Data Review, Signal Mapping Review, STANDARD, Import Sources and Change Audit Log.

## 0.6.5

- RMU Data Review and Signal Mapping Review now support spreadsheet-style cell/range selection.
- Drag selects a rectangular block; Ctrl adds/removes non-contiguous blocks; Shift extends the range.
- Clicking an empty grid area clears selection.
- Clicking outside the active grid clears both selected cells and the current-cell marker reliably on Windows.
- Removed forced single-row selection and row-click `selectRow()` behavior from the two review grids.
- Selection remains outline-only so business/status cell backgrounds are never replaced.


## 0.6.4

- Renamed visible business modules to **RMU Data Review** and **Signal Mapping Review**.
- Unified Excel export into one five-sheet review workbook.
- Export sheets are exactly: `RMU Data Review`, `Signal Mapping Review`, `STANDARD`, `Import Sources`, `Change Audit Log`.
- Signal Mapping Review preserves the customer source worksheet and appends Review / Comments metadata on the right without shifting source columns.
- STANDARD is preserved directly from the selected site REPORT workbook.
- Customer/helper sheets such as Sheet1/temp/Sheet2/Sheet3 are removed from the exported deliverable.

## 0.6.3

- Unified all table headers to a neutral gray/blue hierarchy; business colors are now reserved for data status.
- Removed the duplicate page-level Run Comparison button; the global top-bar action remains.
- Added an `Index` merged group above Comparison `No.` / `RMU`.
- Added an `RMU` merged group above DB Smart `RMU_NO` / `Type`.
- Selection styling now uses an outline rather than a blue fill so row status colors remain visible.
- Preserved Comparison neutral review block and FALSE-cell emphasis.


## 0.6.2

- Fixed DB Smart Report grouped header disappearing after navigating away and back by keeping one persistent `GroupedReportHeader` per table and refreshing its group metadata in place.
- Added a Comparison row-color legend with the meaning of Pass, NAME, FEEDER, SMART, TYPE and FEEDER+TYPE states.
- Analysis / Remarks / Comments now stay neutral; only FALSE Analysis cells are highlighted.
- Row-level business colors now start at No./RMU and continue through all source-data columns.
- Retained all v0.6.1 DB Smart review, Site Repository, Audit, Snapshot and release features.

## 0.6.1
- Moved the Comparison review block to the far left: Analysis → Remarks → Comments → No. → RMU.
- Added a first-class DB Smart Report page that reads the selected site's REPORT.xlsx directly.
- Supports both `DB-smart report` and legacy `DB-smsrt report` worksheet names.
- Added DB Smart row review status, comments, source-read-only behavior, search/filtering and column visibility.
- DB Smart review metadata is stored in project.db and written to the shared audit log.
- Added a dedicated `db_smart.py` service boundary so later DB Smart calculations can replace/enrich the workbook source without rewriting the UI.


## v0.6.0 - Comparison Review Workspace
- Review-first Comparison order: Analysis, Remarks and Comments move to the front of the desktop grid.
- Column visibility dialog with group/field controls and saved presets.
- Analysis mismatch filter and review color system.
- Analysis hover details and automatic consistency remarks.
- Excel DATA export order remains unchanged.

- Reworked shared empty-state layout to prevent wrapped subtitle clipping on Windows/DPI scaling.
- Replaced individually centered labels with a bounded responsive content container.
- Applied the fix to Audit Log and Versions automatically through the shared component.
- Improved normal responsive table header/row sizing for readability.
- Hardened page-header and audit-description height-for-width behavior.


## v0.5.3

- Reworked Analysis NAME / FEEDER / SMART / TYPE into one blank-ignoring consistency engine.
- One non-blank source value evaluates TRUE; all sources blank evaluates blank instead of FALSE.
- NAME compares the available SE / ZENON DB / ZENON SLD XML / ADMS DB / ADMS SLD cabinet names.
- FEEDER compares available source feeders after site-relative normalization and numeric zero-padding normalization.
- SMART normalizes SE equipment classification and source SMART/NORMAL aliases; sources without an explicit SMART value are ignored.
- TYPE compares explicit cabinet types; current ZENON DB DEVICE is included as the cabinet type source.
- Corrected Analysis header spelling from FEEDEER to FEEDER.

## v0.5.2

- Added a shared responsive-table policy for operational tables instead of hard-coded widths that leave large blank areas on wide displays.
- Site Repository now uses a draggable `QSplitter` between Sites and Source Inventory.
- Site Repository columns keep compact status/date/size fields while `Detected File` stretches to consume remaining width.
- Audit Log now lets `Reason` consume remaining width while identity/timestamp columns remain predictable.
- Versions now lets `Description` consume remaining width.
- Added explicit empty states for Audit Log and Versions instead of presenting a large blank table.
- Added per-pixel table scrolling and minimum header sizes for smoother 1366/1920/2K behavior.
- Comparison intentionally remains a fixed-width 54-column engineering DATA grid with horizontal scrolling and grouped headers.
- Preserved v0.5.1 Site Repository workflow and ABN/ABN2 exact feeder-token XML filtering.

## v0.5.1

- Removed manual **New Project / Open Project** from the primary UI. A repository site folder is now the working identity; its private app workspace is created/opened automatically.
- Top bar now exposes Site Repository / Refresh Sources / Run Comparison instead of project actions.
- Added site-aware zenOn XML filtering using the parsed feeder from `SubstituteDestination`. Exact token matching prevents `ABN` from matching `ABN2`.
- Added SE feeder suffix matching as an additional positive signal for site filtering.
- Combined XML exports such as `ABN-ABN2.XML` are supported and filtered at runtime for the selected site.
- XML auto-discovery can select a combined XML by exact site token even when more than one XML exists in the site folder.
- Repository remembers the last selected site.
- Generated `ZENON-SLD.csv` and Comparison use the same filtered XML dataset.
- Added regression tests for ABN/ABN2 isolation and combined XML discovery.

## v0.5.0

- Introduced Site Repository architecture: one root folder, one direct child folder per site.
- Added canonical source-name detection plus legacy site-prefixed filename compatibility.
- Added live source status (`NEW`, `UPDATED`, `CURRENT`, `MISSING`, `OPTIONAL`).
- Added SHA-256 source fingerprinting and timestamped source snapshots.
- `Run Comparison` re-scans live site files at execution time before synchronization/parsing.
- Kept the repository read-only and application workspace separate for audit/reproducibility.
- Added Advanced Manual Import as an exception path for non-standard deliveries.

## v0.4.3

- Fixed SE feeder mapping: official SE detail header `FEEDER` now maps to `From SE > Feeder` (legacy `FEEDR` remains compatible).
- `Run Comparison` imports/replaces newly selected source files before parsing, preventing stale workspace data from being reused.
- Added source import service and microsecond archive names.
- Added regression coverage for `SS / FEEDER / EQUIPMENT / EQUIP. TYPE / OH / UG`.

## v0.4.2

- Aligned Comparison and exported DATA headers to the uploaded `ADF-REPORT-v2.0.xlsx` exactly through column BA.
- Added `Screen name` as the first field under `ZENON SLD XML` (AC), sourced from Zenon XML `Picture/@ShortName`.
- Shifted downstream source groups to match the ADF template: ADMS DB AG:AO, ADMS Channel AP:AR, ADMS SLD AS:AV, Analysis AW:AZ, Remarks BA.
- Preserved the application-owned SE review `Comments` column as BB.
- Generated `ZENON-SLD.csv` now names the XML picture field `Screen name`; legacy `Picture` input remains accepted.
- Bundled `ADF-REPORT-v2.0.xlsx` as the default customer report template.
- Updated build preflight and packaged EXE self-test to require the latest ADF template.

## v0.4.1
- Standardized BAT-as-launcher / PowerShell-as-orchestrator build architecture.
- Added formal `setup.bat`, `build.bat`, `release.bat`, and `clean.bat` entry points.
- Added `scripts/common.ps1` shared build helpers and strict PowerShell execution.
- Added pinned runtime and build lock files for reproducible Windows x64 releases.
- Build now asserts EXE existence and plausible size, then executes packaged self-test.
- Release now verifies ZIP, manifest and SHA256 outputs before success.
- Added separate timestamped build and release logs.
- Legacy build/install BAT files are compatibility redirects only.
- Preserved Audit Log, SE Comments, row highlighting, grouped DATA header, SQLite and source-adapter architecture.

## v0.4.0
- Reorganized source into a production-style `src/` package and separated resources, packaging, scripts, tests and release outputs.
- Fixed PyInstaller relative-resource resolution bug caused by `--specpath` + relative `--add-data`.
- Added checked-in PyInstaller spec with absolute resource paths.
- Added `build.bat` (compile EXE) and `release.bat` (formal release) as separate pipelines.
- Added build preflight, core regression test, EXE existence assertion and packaged EXE self-test.
- Added build logs, BUILD_INFO.json, versioned release directories, manifest and SHA256 checksums.
- Renamed Manual Changes to Audit Log and clarified its immutable traceability purpose in the UI.
- Export audit worksheet renamed to `_Change Audit Log`; legacy `_Manual Changes` is removed/replaced on export.
- Retained SE Comments, whole-row review highlighting, DATA A:BA layout, SQLite audit storage and source-adapter architecture.

## v0.3.3
- Added whole-row selection/highlight and SE Comments column.

## v0.8.3 - Build Pipeline Invocation Fix

- Fixed the formal `build.ps1` Python invocation wrapper so arguments are always passed explicitly through `-PythonArgs`.
- Removed the `$Args` parameter name collision with PowerShell's automatic `$args` variable.
- Added a guard that refuses to launch Python with an empty argument list, preventing accidental interactive `>>>` sessions during release builds.
- Added an explicit `python -m pip --version` sanity check before locked dependency installation.
- Hardened virtual-environment creation argument forwarding.
- Documented the recommended one-line build command using process-scoped `ExecutionPolicy Bypass`; activating `.venv` manually is not required.
