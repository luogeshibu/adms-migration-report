# v0.8.196 — Equipment Review Interaction Performance

- Equipment Data Review now prepares one canonical unfiltered in-memory review session per active site/profile. Search, Review Status filters and Analysis filters no longer spawn a worker process, reopen source workbooks, requery whole SQLite maps or rebuild thousands of QTableWidgetItems.
- Search/filter controls now hide/show already-rendered rows locally. **Show All** also clears filters locally instead of reconstructing the grid.
- Added direct in-memory lookup caches for equipment rows, enriched review entries, row indexes, Review records and Resolution maps. Single-row actions no longer fall back to `build_equipment_source_view()` after the initial render.
- Review Status changes are optimistic: the row, locator color and counters update immediately, then the durable Review/lifecycle/audit changes are written on a background ProjectStore connection in a batched transaction. Failed writes reconcile with one exceptional full refresh.
- Summary and Resolution progress counters use cached Analysis/Review/Resolution state instead of whole-table SQLite queries and repeated Analysis calculation.
- Row-selection lifecycle reads are debounced to 220 ms and use the preloaded Needs Action tracking key set. Equipment that never entered Needs Action no longer opens lifecycle/audit tables merely because the reviewer clicked the row.
- Site/source invalidation explicitly clears the hot review session; ordinary reviewer edits keep the session warm.
- Comparison semantics, selectable Strict / Ignore Blank modes, Resolution/Review Status decoupling, append-only Comments, Needs Action lifecycle, exports, source/profile configuration and column sizing are unchanged.
- Regression gate: **395 unittest tests passed**; targeted v0.8.193/v0.8.195/v0.8.196 performance/workflow tests **18 passed**; `compileall` passed.

# v0.8.195 — Custom Resolution Save Fix

- Fixed the `Others · custom resolution` branch in Equipment Data Review. The dialog previously referenced an undefined `field_label` while building the custom Resolution description, so clicking **Save Resolutions & Comments** could fail before any SQLite write started.
- The custom branch now resolves the current configured/display Analysis field label inside the decision loop before building `decision_description`.
- A custom Resolution value and a new Customer Comment can now be saved together in one existing batched Resolution transaction.
- A blank New Customer Comment continues to preserve the latest saved comment and does not append a duplicate review note.
- Added regression coverage for the exact `OTHER` UI payload path and a ProjectStore persistence smoke test for custom Resolution + Customer Comment.
- No comparison, Review Status, Needs Action lifecycle, source/profile, export, Checked-performance, or column-sizing semantics changed from v0.8.194.
- Regression gate: **387 unittest tests passed**; targeted custom-resolution tests **4 passed**; targeted Resolution/comment workflow tests passed; `compileall` passed.

# v0.8.194 — Optional Signal Mapping Export + Async Review Writes

- Formal Excel export no longer fails when Signal Mapping sources are not configured. Missing `ZENON-ADMS-IOA` / `ADMS-SLD` now produces a `Signal Mapping Review` sheet marked `NOT CONFIGURED`; Equipment Data Review, STANDARD, Import Sources and Change Audit Log still export normally.
- The fixed five-sheet workbook shape is preserved for downstream users, but Signal Mapping is no longer a hard dependency of Equipment Data Review export.
- Excel generation now runs on a background worker connection so the Qt GUI stays responsive while OpenPyXL builds/saves the workbook.
- Excel/PDF pre-export readiness uses the lightweight cached row count instead of decoding every comparison row just to determine whether data exists.
- Equipment Review export preloads the complete Review map and Resolution map once. It no longer executes per-equipment SQLite queries for manual comments/resolution summaries (removes the export N+1 query pattern).
- Equipment Row Locator `Checked` changes are now debounced for 60 ms, collected, and persisted by a background ProjectStore connection in one transaction; the checkbox paints immediately and no SQLite writer-lock wait occurs on the GUI thread.
- Failed background Check writes are reconciled from storage; successful writes keep Audit/Dashboard/Site History/Export on the existing lazy-refresh policy.
- No changes to selectable Strict / Ignore Blank comparison semantics, Review Status / Resolution separation, Comments, Needs Action lifecycle, profiles, source mapping, or auto/manual column sizing.
- Regression gate: **383 unittest tests passed**; targeted v0.8.192-v0.8.194 performance/export tests **17 passed**; `compileall` passed.

# v0.8.193 — Review Check Hot-Path Performance

- Equipment Data Review `Checked` clicks no longer synchronously rebuild Audit, Site History or Export tables.
- Dashboard, Audit, Site History and Export are marked dirty and refreshed only when those pages are opened.
- A successful Check click does not rebuild the Equipment Review grid or recalculate unrelated comparison/resolution counters.
- Ordinary equipment without any Needs Action lifecycle skips construction of the rich lifecycle snapshot when Check changes; the audit `changes` row is still persisted.
- Equipment that already has formal lifecycle history still records `CHECK_CHANGED` events with the existing snapshot semantics.
- Signal Mapping `Checked` uses the same lazy secondary-page refresh policy.
- No comparison semantics, Review Status, Resolution, Comments, lifecycle, export, profile, source, or column-sizing behavior changed from v0.8.192.
- Regression gate: **377 unittest tests passed**; targeted current check/comparison tests **12 passed**; `compileall` passed.

# v0.8.192 — Selectable Comparison Modes

- Added a site-level **Default Comparison Mode** for configurable Equipment Data Review.
- Added per-Comparison-Field mode override: **Use site default**, **Strict equality · blank participates**, or **Ignore blank values**.
- Strict mode preserves v0.8.191 behavior: every bound source participates; all equal including all blank = TRUE; blank/non-blank mix or any other difference = FALSE.
- Ignore Blank mode restores the historical behavior: blank values are excluded; one remaining value = TRUE; equal remaining values = TRUE; different remaining values = FALSE; all blank = N/A/blank.
- Missing rows in a bound source are treated as blank before the selected comparison mode is applied. Unbound sources never participate.
- Existing v0.8.191 site configs migrate safely to Strict as their site default. Existing rules inherit that default unless explicitly overridden.
- Reusable global profiles and site inheritance preserve both the site default mode and per-rule overrides.
- Chinese UI includes comparison-mode labels/help.
- No change to Review Status/Resolution separation, Needs Action lifecycle, comments, source discovery, direct live-source reads, exports, Signal Mapping, or column sizing.

# v0.8.191 — Strict Blank-Aware Configurable Comparison

- Configurable Equipment Data Review comparisons now treat blank as a real comparison value for every bound source.
- All bound values equal => TRUE, including all blank.
- Any blank/non-blank mix => FALSE.
- Any different non-blank normalized value => FALSE.
- A missing row in a bound source participates as blank; an unbound source remains excluded from that rule.
- Comparison tooltips now show `<blank>` explicitly and explain the strict rule.
- No changes to Review Status, Resolution, Comments, lifecycle, profiles, exports, Signal Mapping, or column sizing.

# v0.8.190 — Content-Aware Equipment Review Column Auto-Fit

- Equipment Data Review columns that have never been manually resized now auto-fit after the full current equipment data set is rendered.
- Auto-fit uses each schema width as a minimum baseline, the header text, an evenly distributed bounded sample and the longest textual candidate for that field, with a 520 px maximum to prevent pathological values from exploding the grid layout.
- Width calculation uses the full unfiltered equipment data set, so changing search/filter controls does not make column widths oscillate.
- Existing manual widths remain authoritative and are never overwritten by automatic fitting.
- Double-clicking a main-grid header clears that column's manual-width override and immediately returns it to content-aware auto-fit.
- Header tooltips explain drag-to-resize and double-click-to-fit behavior in English and Simplified Chinese.
- Comparison, Review Status, Resolution/Comments, Needs Action lifecycle, configurable sources/profiles, exports, Signal Mapping and v0.8.189 Resolution/Status decoupling are unchanged.
- Regression gate: **361 unittest tests passed**; `compileall` passed.

# v0.8.189 — Manual Review Status / Resolution Decoupling

- Equipment Review **Resolution** and **Review Status** are now fully independent. Selecting `Use SE`, `Use ZENON SLD`, `Use ADMS DB`, another source, `Accept Exception`, `Needs Action` as a resolution record, or `Others` no longer auto-closes or auto-opens the equipment review.
- Removed the old ADMS-DB coupling that automatically changed Review Status based on whether the selected/normalized Resolution value matched ADMS DB.
- A reviewer-owned `NEEDS ACTION` state remains `NEEDS ACTION` after any Resolution/comment save and stays tracked until the reviewer explicitly changes Review Status.
- `CLOSED` and `UNREVIEWED` are likewise changed only through the explicit Review Status workflow, not by Resolution source/value selection.
- Updated Resolution-dialog help text (English/Chinese) to explain that Resolution records the agreed handling while Review Status is a separate manual workflow decision.
- Existing historical statuses are preserved; the release does not rewrite old project history.
- Comparison, Resolution storage, append-only Comments, lifecycle/audit, source refresh, profiles, exports, Signal Mapping and v0.8.188 resizable-column behavior remain unchanged.
- Regression gate: **356 unittest tests passed** in isolated user/project-data sandboxes; compileall passed.

# v0.8.188 — Manual Equipment Review Column Resize

- Equipment Data Review main-grid columns now use interactive header sections instead of fixed-width sections. Reviewers can drag any column divider left/right to inspect long values such as `processed_name`, Functional Location, manufacturer names, IP fields, or arbitrary dynamic Excel/CSV columns.
- The existing schema widths remain only the initial defaults for newly seen columns.
- Manual widths are remembered by stable column key in QSettings and reapplied after source refresh, site switching, dynamic schema rebuild and application restart.
- Width persistence is debounced so dragging a column does not cause repeated synchronous settings writes.
- Hide/show operations do not overwrite a remembered width with a temporary zero-width section.
- No comparison, review lifecycle, comments/resolution, source mapping, profile, export, recursive discovery or Signal Mapping behavior changed from v0.8.187.
- Regression gate: **353 unittest tests passed**; compileall passed.

# v0.8.187 — Review Save Responsiveness

- Replaced ambiguous Qt `OK`/`正常` item-dialog confirmation with explicit `Save / 保存` and `Cancel / 取消`.
- Removed eager full Site History reconstruction from Equipment Resolution save, manual Comment save and Review Status save hot paths.
- Added a one-row `rmu_review_record()` lookup and used it for single-equipment snapshots/repaints, avoiding repeated 2,000+ row review-table scans during edits.
- Manual comment save now repaints only the affected row and selected-equipment lifecycle; review/resolution counters are left untouched because a comment does not change them.
- Site History, Dashboard, Versions/Audit and Export are invalidated lazily and rebuilt when those pages are opened.
- No changes to Analysis, source comparison, Comments history, Needs Action lifecycle, PDF/Excel export, profile inheritance or Signal Mapping logic.

# v0.8.186 — Recursive Site Source Discovery

- Fixes the station-list false warning **“未发现表格文件 / NO TABULAR FILES”** when valid CSV/XLSX/XLSM inputs are stored below nested site folders such as `Equipment/` or `SignalMapping/`.
- Station availability now checks the actual site tree recursively instead of relying on the legacy root-only role resolver.
- Configurable source-pool discovery is now recursively unbounded by default; reviewer-created nested folders remain discoverable at any depth.
- Office temporary lock files (`~$...`) and hidden/archive/backup folders remain ignored.
- No comparison, review lifecycle, export, profile/inheritance, mapping, or report logic changed from v0.8.185.
- Regression gate: **343 unittest tests passed**; compileall passed.

# v0.8.185 — Configurable UX + Explicit Export Paths + All-Equipment Tracking

- Refined the configurable Equipment Data Review source/profile UI so long live paths, source controls and reusable-profile controls remain readable and usable.
- Migration Report Excel and sign-off PDF exports now always use an explicit Save As dialog; the application no longer silently exports formal deliverables to the default project reports folder.
- Persisted the actual external Migration Report export path/time so Dashboard delivery readiness follows user-selected export locations while retaining backward compatibility with legacy internal reports.
- Generalized durable Needs Action tracking from RMU-only presentation to all equipment types. Any equipment entering NEEDS ACTION remains tracked through the existing lifecycle until explicitly CLOSED.
- Generalized site-history tracking and sign-off PDF summaries/registers to Equipment rather than RMU-only terminology/logic.
- Source recognition is now optional priority/hint behavior rather than a filename contract: arbitrary filenames remain valid and explicit user assignment always wins.
- Source-recognition categories are extensible and may include custom categories beyond the historical SE/ZENON/ADMS/IOA set.
- Preserves v0.8.184 Chinese localization/unlimited source count, v0.8.183 reusable profiles/inheritance, v0.8.182 direct live-source reads/no source copies and global no-wheel safety.
- Regression gate: `PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"` = **338 tests passed**; `python -m compileall -q src tests` passed.

# v0.8.184 — Chinese UI Localization + Unlimited Equipment Source Status

- Completed Chinese presentation coverage for the configurable Equipment Data Review workflow introduced in v0.8.178-v0.8.183, including source-pool controls, reusable-profile/inheritance controls, source participation/version/file-family controls, configuration help text, validation messages and site-source placeholder rows.
- Engineering data stays literal by design: physical Excel/CSV headers, filenames, worksheet names, user-defined module/profile names and comparison-field names are never translated or rewritten.
- Removed the legacy fixed `x/6` station-list readiness contract. Equipment Data Review source count is now presented as fully configurable per site; the station list shows only whether tabular files are available / configurable review is configured.
- Configurable project readiness now evaluates the actual enabled Equipment sources and saved comparison rules instead of requiring legacy fixed source roles. Disabled configurable sources do not make the project incomplete.
- Signal Mapping retains its own existing required inputs and algorithm; this release does not weaken Signal Mapping validation.
- Site Data Sources explanatory text and configurable placeholder rows are localized in Chinese and no longer describe a fixed five/six-source Equipment contract.
- Preserves v0.8.183 reusable profiles/inheritance, v0.8.182 live direct-read/no-copy source behavior and no-wheel selection safety, plus all review lifecycle/audit/Excel/PDF/sign-off logic.
- Regression gate: `PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"` = **333 tests passed**; `python -m compileall -q src tests` passed.

# v0.8.183 — Reusable Comparison Profiles + Site Inheritance

- Added application-wide named Equipment Data Review comparison profiles stored in `global_settings.db`.
- A reusable profile contains logical source roles/order/titles, file-family hints, worksheet/header defaults, Key / Index defaults, field visibility defaults and comparison rules/bindings.
- Reusable profiles never store another station's physical CSV/XLSX/XLSM path. Applying a profile preserves the target station's existing live source paths and can auto-bind missing roles from that station's own file pool by filename family.
- Existing station source ids and enable/disable state are preserved when a matching role is synchronized, protecting source/audit continuity and station-specific participation choices.
- Site-only extra Equipment sources are retained when a profile is applied.
- Added **Configuration Reuse / Inheritance** UI with Local vs Inherit modes, named profile selection, **Apply / Sync**, **Save Current as Profile...**, **Update Selected Profile**, and **Delete Profile**.
- Inheritance is deliberately explicit-sync rather than silent live propagation: a global profile update is shown as available, but reviewed station data is not rewritten until the user applies/syncs and saves that station.
- A profile can also be applied once and the site switched back to Local, providing a one-time clone workflow.
- Preserves v0.8.182 direct live-source reads/no-copy behavior and global no-wheel input protection, plus all review lifecycle/audit/report logic.

# v0.8.182 — Live Source Direct Read + No-Wheel Selection Safety

- Configurable Equipment Data Review sources are now live file references. CSV/XLSX/XLSM files are read directly from their site/original path; the configurable workflow no longer copies source workbooks into Project Data/workspace.
- Existing v0.8.178-v0.8.181 configurations that still point at timestamped internal source copies are transparently rebound to the remembered/original repository file when it can be resolved; saving the configuration persists the live reference. Historical copies are not deleted.
- Active direct sources are watched by path/size/mtime. In-place edits and AUTO-family version switches are re-read in the background; failed/locked reads do not advance the watcher baseline.
- Signal Mapping file assignments use the same live-reference principle while retaining the existing Signal Mapping algorithm.
- Application-wide safety guard consumes mouse-wheel events on every QComboBox and QAbstractSpinBox, including dynamically created dialogs, so scrolling can never silently change a selected option/value. Normal page/table scrolling is unchanged.
- Review state, lifecycle, audit, project.db, comparison rules, TRUE/FALSE semantics, report export and sign-off remain unchanged.

# v0.8.181 — Flexible Site File Pool and source membership

- Added a live **Available Site Files** pool to Equipment Data Review configuration. Refresh scans the active station folder (including optional `Equipment/` and `SignalMapping/` subfolders) for CSV/XLSX/XLSM without silently enrolling newly discovered files.
- Any discovered file can be explicitly **Add → Equipment**, remain **Unused**, or be assigned to one of the existing Signal Mapping input roles. Discovery and review participation are now separate concepts.
- Equipment sources can be **enabled/disabled at any time** without deleting their configuration, comparison bindings, title, worksheet, key, field visibility, or physical file. Disabled sources are excluded from review row generation, coverage and TRUE/FALSE comparison.
- Every Equipment source remains freely renameable through **Module Title**.
- Added per-source version selection: **Latest file in family (AUTO)** or **Pin this exact file**. AUTO groups forgiving filename families (`NAME.xlsx`, `NAME (2).xlsx`, `NAME-V2.xlsx`, etc.) and resolves the highest explicit V/Rev version first, then newest modification time.
- The selected/resolved physical path is shown as **Active Source File**. A reviewer can switch between AUTO and pinned behavior without recreating the source.
- Signal Mapping file assignments can also use AUTO family or pinned mode; its existing comparison/mapping algorithm is unchanged.
- Recommended folder organization is supported but optional: station-root files continue to work; users may organize source files under `Equipment/` and `SignalMapping/` without changing the comparison engine.
- Preserves v0.8.180 configurable Validation-path fix, v0.8.179 source-selection synchronization, and all existing review lifecycle/audit/report logic.

# v0.8.179 — Configurable source selection synchronization fix

- Fixed the Equipment Data Review configurable-source dialog where clicking a different source could change the highlighted source in the left list while the middle editor still showed another source's file/path/worksheet/key.
- Root cause: the previous editor was saved during Qt `currentItemChanged`, and that save rebuilt/restored the source `QListWidget` after signals were unblocked, causing a nested synthetic selection change inside the original user selection event.
- Source-list rebuild now keeps signals blocked through programmatic selection restoration.
- Source switching now saves the previous editor by its explicit source id without rebuilding the list, then loads the exact newly clicked source and refreshes rules/validation once.
- Added defensive Header Row normalization while committing a source editor.
- This is a UI/state synchronization hotfix only. Arbitrary source count, user-selected keys, configurable comparison bindings, dynamic Equipment Data Review rendering, TRUE/FALSE semantics, lifecycle, audit, Excel/PDF and Signal Mapping behavior remain unchanged from v0.8.178.

# v0.8.178 — Configurable Equipment Data Review sources

- Replaced the fixed five-source Equipment Data Review input contract with arbitrary site-local CSV/XLSX/XLSM sources.
- Added per-source worksheet, header-row and Key / Index selection. Each source can use a different physical key field.
- Added user-defined comparison rules that bind any physical field from any participating source. Differently named headers can therefore represent the same logical comparison.
- Preserved the historical blank-ignoring comparison semantics: no usable value = blank/N/A state, one available value = TRUE, all available equal = TRUE, any available difference = FALSE.
- All physical fields default visible for newly configured sources. Per-site/per-source hidden-field choices affect presentation only.
- Source group titles default from filenames and are user-editable; Equipment Data Review columns and Analysis columns are generated dynamically from configuration.
- Generalized source coverage, review mismatch filters, resolution candidates, Excel export, PDF issue labels and source-change lifecycle projection to configured sources/rules without changing the existing review lifecycle.
- Kept Signal Mapping and all non-source comparison workflows on the v0.8.177 behavior.
- Legacy projects do not switch modes merely by opening the configuration editor; configurable mode activates only after explicit Save.
- Added v0.8.178 regression coverage for arbitrary filenames/headers, per-file keys, differently named comparison fields, dynamic rendering, hide/show and legacy-bootstrap cancel safety.
- Validation gate: `PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py"` = **305 tests passed**; `python -m compileall -q src tests` passed.
- Real-data smoke test with four uploaded heterogeneous workbooks produced **2,575 union-key review rows** and dynamic `1/4` … `4/4` coverage, confirming that source count and field names are not hard-coded.

# v0.8.177 — Isolated formal-build regression environment

- Fixed a formal Windows build failure caused by regression tests reading the operator's real application-global Map Fields settings from `global_settings.db`.
- `build.ps1` now creates a clean build-local test sandbox and temporarily sets both `MIGRATION_REPORT_TOOL_USER_DATA_ROOT` and `MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT` while unittest regression runs.
- Production mappings/visibility/project data are never used by, or modified by, the build regression suite.
- The original environment is restored in a `finally` block and the temporary sandbox is removed after tests.
- Added a regression contract so later releases cannot silently return to profile-dependent build tests.
- No runtime equipment-comparison or source-mapping business logic is changed.

# v0.8.176 — Generic equipment identity in SYSTEM mapping

- Replaced the legacy user-facing SYSTEM field label `RMU` with canonical `Equipment Name` for equipment-source mapping.
- Kept internal key `rmu` and `RMU` physical-header aliases for backward compatibility with existing project databases, review history and source files.
- System Mapping Assignments now deliberately ignores presentation/display aliases when naming protected semantics.
- Protected mapping confirmation now refers to equipment comparison results rather than RMU-only comparison results.

# v0.8.175 — Map Fields settings sync across all stations

- Makes source-field Show/Hide preferences application-global by source/App table, matching the already-global Source Field mappings, App display names, USER columns and column order.
- A visibility change saved for ADMS SLD (or any other source type) at one station is immediately reused by every other station; stale per-site hidden-field settings can no longer override the global choice.
- Preserves station-local physical source file selection, Excel sheet selection and live resolved source values.
- Promotes one legacy site-local visibility preference only when no global preference exists, then keeps the global value authoritative.
- Adds regression coverage for cross-station mapping/display/visibility/order synchronization and SYSTEM-field visibility protection.

# v0.8.174 — Unlock SYSTEM mappings must actually remap missing semantics

- Fixed a dead-end in source-driven Map Fields: when a required SYSTEM field had no built-in alias in the physical header, its canonical row did not exist, so clicking **Unlock System Mappings** could not assign it.
- Added a dedicated **System Mapping Assignments** editor that lists all protected SYSTEM semantics and lets the reviewer bind them to any live physical header.
- The main Map Fields grid still obeys the one-physical-column/one-App-row contract; successful SYSTEM assignment promotes the existing physical row instead of creating a phantom row.
- The unlock button remains reusable as **Edit System Mappings...** rather than becoming disabled.
- Protected mapping confirmation now compares complete SYSTEM state, including initially-missing fields, so `Missing -> Manual` changes are always confirmed on Save.
- Improved schema-error guidance for unlocked and locked states.

# v0.8.173 — Needs Action source-version change tracking

- Equipment/RMU rows that have ever entered **Needs Action** now retain physical source-value changes across later source refreshes/Validation runs.
- The comparison engine stores compact source provenance (active filename/version/hash metadata) with each calculated row, then compares the previous calculated source values with the newly calculated values before replacing the live projection.
- Only values that actually changed are appended to the latest equipment lifecycle as `SOURCE_VALUE_CHANGED`; unchanged fields create no history noise.
- Source changes do not reopen a closed case. They append to the latest historical equipment case; a later explicit Needs Action still creates the next case number.
- Source-change rows identify both the physical source and the field, e.g. `ADMS SLD · TYPE`, with old/new values and source filenames in the reason text. Hidden optional App/source fields remain eligible for audit because hiding is presentation-only.
- AUTO source selection remains deterministic: explicit semantic `V` versions win (`V3 > V2.9 > V1`); file modification time is only a tie-breaker within the same semantic version. If no valid V-version exists, AUTO falls back to the newest matching unversioned/canonical source. Explicit PIN/MANUAL selection still overrides AUTO.

# v0.8.172 — Complete post-Needs-Action status lifecycle

- Once an equipment/RMU has ever entered **Needs Action**, every later review-state transition is retained in its lifecycle, including transitions to **Unreviewed** after the formal case has already been closed.
- A post-close `UNREVIEWED` or `CLOSED` state change does **not** reopen the old formal case; it is appended as a `STATUS_CHANGED` event on the latest historical case. A later **Needs Action** still opens the next case number.
- Automatic source/validation changes that reset an already-reviewed RMU to `UNREVIEWED` are also written into the lifecycle when Needs Action history exists.
- The compact tracker now labels the case column **Equipment Case** and renders values such as `8881B-001`, making the per-equipment case numbering explicit.

# v0.8.171 — Default-hide optional source fields

- Map Fields now starts with every optional physical/App field hidden by default; only SYSTEM calculation fields are visible on first use.
- Source-driven fields discovered later from new Excel/CSV headers also default to hidden until the reviewer explicitly enables them.
- Visibility remains fully manual: **Show All Fields** persists an explicit empty hidden set, so later openings keep those optional fields visible.
- No mapping, source data, audit history, or system-calculation behavior is removed by hiding fields.

# v0.8.170 - Review-draft export compatibility - 2026-09-10

- Fixed a workflow regression where `validation_required_after_source_import=true` hard-blocked both Excel and sign-off PDF export even though the Report Export page explicitly said review-draft export was available.
- Pending Validation now produces an explicit confirmation dialog instead of a hard stop.
- Review-draft PDF output is visibly watermarked/bannered and its filename contains `_DRAFT_`.
- Draft PDF metadata stores `document_status=REVIEW DRAFT` and `validation_required_at_export=true`; signed-copy attachment rejects draft reports.
- Projects with no calculated review rows still require one successful Validation before any report can be exported.

# v0.8.169 - PDF issue register clarity and page-flow fix - 2026-09-09

- RMU Need Action PDF now renders **one row per issue type/field** instead of compressing FEEDER/SMART/TYPE/etc. into one tall multi-line RMU row.
- Replaced the ambiguous `Modification Item` column with **Issue Type**.
- Manual `Needs Action` rows no longer export `Needs Action` as if it were a field name. The report conservatively derives categories such as FEEDER, SMART, TYPE, IP, BRAND, DEVICE DATA or SOURCE DATA from the reviewer text; unknown cases fall back to `MANUAL REVIEW`.
- Removed `TBD` from the formal PDF wording. Missing targets are shown as **Not specified**; missing ADMS DB values as **Not available in ADMS DB**; `OTHER` resolutions use **See Remarks**.
- Added table row page-break protection and repeated table-header CSS for all formal action registers. Combined with one-issue-per-row output, this prevents the split-row/verification-box spill shown at page boundaries.
- Added `RMUs / issues` counts to the RMU Need Action heading.
- Build regression gate: 267 unittest cases passed; compileall passed.

# v0.8.168 build regression fix — 2026-09-09

- Fixed the Windows `build.ps1` release gate: the product code was valid, but 34 historical `unittest` contract assertions were still pinned to older release metadata/UI wording (`0.8.143`, schema 11, RMU-only labels, one-row render batch, and pre-source-driven mapping copy).
- Updated those historical regression assertions to the current v0.8.168 contracts without changing application business logic.
- Current persistent database schema remains `12`; no database downgrade or data migration rollback was introduced.
- Full build regression command now passes: `261 tests` / `OK`.
- `compileall` passes for `src` and `tests`.

# v0.8.168 — Map Fields drives Equipment Data Review columns

- Equipment Data Review source groups now mirror each active physical source header instead of the static canonical schema.
- If SE has exactly `SS, FEEDER, EQUIPMENT, EQUIP. TYPE, OH / UG`, the SE review group shows exactly those five App columns; absent `Device Type`, `TYPE`, `IP`, etc. no longer appear as phantom columns.
- The Show checkbox in Map Fields is the authoritative visibility control for physical SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD fields.
- SYSTEM calculation fields remain forced visible when their physical source column exists; a missing physical source field is reported by validation but does not manufacture a review column.
- Newly discovered physical headers keep the source-driven rule: default App label = physical header; after Map Fields Save the corresponding review column appears automatically.
- The generic Equipment Data Review Columns dialog now controls only App/meta groups (Index, Source Coverage, Analysis, Remarks, Resolution), avoiding two conflicting visibility controls for source fields.
- Saving Map Fields updates the open review header immediately; source row values continue refreshing in the background.
- Added Chinese localization for the source-driven mapping explanation/status text.

## v0.8.167 — Source-driven live columns

- Map Fields now renders exactly one row per physical CSV/XLSX header in the active source sheet.
- Built-in SYSTEM semantics attach to the matching physical row; missing physical columns no longer create phantom mapping rows.
- Unmatched physical headers become automatic App fields with the physical header as the default App name.
- New source columns appear automatically after the source file is saved; the dialog watches file metadata and re-reads only when the file changes.
- App names remain editable and persisted; source mappings remain independent from visibility.
- SYSTEM calculation fields remain forced visible and mapping-protected.
- USER fields that are absent from the current station/file remain persisted globally but are not rendered in the current source-driven view.

- The visible “+ Add App Column” action is removed from Map Fields so the row count cannot exceed the physical source-column count.
- Source-discovered optional rows keep their physical Source Field fixed; users rename the App label or change visibility instead of creating duplicate remaps.
