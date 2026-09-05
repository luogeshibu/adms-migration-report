# v0.8.164 — Comprehensive Simplified-Chinese UI audit

- Completed a full presentation-layer Chinese audit across Review Versions, Site History, Report Export, Change Audit, Signal Mapping workflow UI, setup/lifecycle dialogs, source-mapping guidance, tooltips and runtime status messages.
- Added Chinese translations for workflow/meta table headers such as Revision History, Issue/Action Register, lifecycle/tracking, audit history and PDF sign-off history.
- Fixed runtime-refresh translation gaps: Site History, Report Export and Signal Mapping are retranslated after dynamic labels are regenerated, so Chinese pages no longer revert to English after refresh.
- Added dynamic localization for user/site header text, RMU follow-up/lifecycle counters, sign-off counters/history and draft delivery-status messages while preserving identifiers and file names.
- Centralized transient status-bar localization so messages generated after page construction also follow the active interface language.
- Replaced unsafe global Chinese-substring reversal with a restricted embedded-prose contract plus structured dynamic patterns; this prevents Chinese -> English switching from corrupting phrases such as “未关闭 / 已关闭”.
- Added a static visible-literal audit regression so future hard-coded English UI captions/tooltips are detected unless they are explicit engineering/source identifiers.
- Kept the existing engineering-language boundary unchanged: `SE`, `ZENON DB`, `ZENON SLD`, `ADMS DB`, `ADMS SLD`, physical source headers, App/internal field keys and auditable table-body values are not translated.
- Preserved v0.8.163 Field Mapping dialog fix and all v0.8.162 Device Type / Type semantics. No database, mapping, Analysis, Review, Resolution or lifecycle business logic changed.

# v0.8.163 — Field Mapping dialog startup fix

- Fixed `NameError: NoWheelComboBox is not defined` when opening **Map Fields / 字段映射**.
- Restored the shared no-mouse-wheel `QComboBox` used by source-field mapping and derived-table selectors.
- Preserved all v0.8.162 Device Type / Type semantics and source mapping behavior; this is a UI regression fix only.
- Added a regression contract that verifies `NoWheelComboBox` is defined before `SourceMappingDialog` and is used by `_source_combo()`.

# v0.8.162 — Device Type / Type semantic split across all equipment sources

- Equipment Data Review now exposes **Device Type** and **Type** as two independent business fields across all five physical source groups.
- `Device Type` means the equipment family/class (`RMU`, `TRANSFORMER`, `LBS`, `FUSE`, `REC`, `SFI`, ...).
- `Type` remains the source equipment subtype/cabinet configuration (`2L1T`, `3L1T`, `OH_TR`, ...); existing TYPE Analysis behavior is unchanged.
- SE, ZENON DB and ADMS DB gained optional canonical `Device Type` mappings. They auto-map only from explicit DeviceType / DEVICE TYPE / EQUIPMENT CLASS style headers and never steal the existing `TYPE` or ZENON DB `DEVICE` subtype columns.
- Source blocks remain source-faithful: if a physical source does not provide Device Type, its Device Type cell stays blank. The global row Device Type still comes from the authoritative ZENON SLD inventory.
- Device Type fields are SYSTEM-protected in Equipment Data Review because they can participate in equipment classification/candidate matching; users cannot hide them.
- No project.db schema change and no existing Review/Resolution/Comments/lifecycle history is rewritten.

# v0.8.161 — Universal review column control + live i18n hardening

- Equipment Data Review now exposes every visible built-in App field from the five Source Mapping schemas, not only the previous fixed subset. USER App columns remain included.
- Equipment Data Review now opens from `All Equipment` as the universal inventory view. RMU is no longer presented as a special `Full Review` mode; RMU, TRANSFORMER, LBS, FUSE, REC, SFI and future DeviceTypes are ordinary source-driven filters over the same comparison model.
- Added stable source-scoped review keys for optional built-in fields, so new App fields can appear without modifying the core comparison schema.
- The Columns dialog is now equipment-generic. Optional/reference columns can be shown or hidden manually; SYSTEM fields used by identity, source coverage, matching, Analysis or validation are locked visible and cannot be hidden.
- Column visibility remains application-global and uses the existing explicit-hidden model: newly introduced App fields are visible automatically until the reviewer hides them.
- ADMS SLD retains separate `Type` and `Device Type`; RMU remains on the same universal five-source comparison path as every other DeviceType.
- Runtime language switching now has a process-local language state, synchronizes QSettings before repaint, retranslates open top-level widgets and flushes paint events. This removes delayed Chinese → English updates in custom-painted headers and dynamic widgets.
- Existing review keys, project.db schema v12, Review/Closed/Needs Action, Resolution, Comments and lifecycle history are unchanged.

# v0.8.160 — Universal Equipment Review + immediate bilingual switching

- Removed the special RMU-only table/render path from Equipment Data Review.
- RMU, TRANSFORMER, LBS, FUSE, REC, SFI and future DeviceTypes use one five-source review layout and the same NAME/FEEDER/SMART/TYPE/IP Analysis + Review/Resolution/Comments/lifecycle workflow.
- Existing RMU review keys/data remain unchanged for upgrade compatibility.
- Fixed zh-CN → English runtime switching so translated widgets revert immediately without restart/page reload.
- ADMS SLD now supports separate `Type`/subtype and `Device Type` source mappings/columns.

# v0.8.159 — Source-name language contract + large Equipment Review performance

Built directly from v0.8.158 / v0.8.157 review-data baseline.

## Changed

- Simplified-Chinese mode now keeps the five physical source names exactly as the engineering contract: `SE`, `ZENON DB`, `ZENON SLD`, `ADMS DB`, `ADMS SLD`.
- Source-role labels such as `SE Equipment` / `SE Equipment List` remain English. Physical CSV/XLSX field names and mapping values remain unchanged.
- Workflow/meta headings in Equipment Data Review remain localized in Chinese, matching the established review layout: Row Locator, Index, Source Coverage, Analysis, Remarks and Resolution can display Chinese while the five physical source blocks remain English.
- Added missing Chinese translations on Settings for setup state, Project Data policy, source-detection guidance, STANDARD management guidance/tooltips and dynamic STANDARD metadata.
- Dynamic setup/status text is translated at assignment time, so switching to Chinese no longer leaves newly refreshed Settings text in English.

## Performance

- Equipment Data Review GUI painting now renders 24 rows per event-loop batch instead of one row per callback.
- Frozen-row `Checked` controls use checkable table items instead of creating a QWidget + QCheckBox for every equipment row.
- Removed unnecessary full-viewport repaints on every hover/active-row change.
- Avoided per-row default-height resize operations and reduced duplicated tooltip strings on ordinary source cells.
- `build_equipment_source_view()` now loads USER custom-field metadata once per source instead of querying SQLite once per source per equipment row. A 1,200-row synthetic five-source build made only 5 metadata reads.

## Compatibility

- Existing RMU and non-RMU Review / Closed / Needs Action / Resolution / append-only Comments / lifecycle history is unchanged.
- Existing review keys and project.db content remain valid; database schema remains v12.
- CSV/XLSX/XLSM source selection, arbitrary filenames, Excel Sheet selection and refresh behavior remain unchanged.
