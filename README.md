## NARI Saudi ADMS Migration Report v0.8.164

v0.8.164 performs a comprehensive Simplified-Chinese presentation audit outside the physical engineering table/source contract. Review Versions, Site History, Report Export, Change Audit, Signal Mapping workflow text, setup dialogs, lifecycle dialogs, mapping guidance and runtime summaries now localize consistently while physical source names/headers and auditable table-body data remain language-neutral. Runtime-refreshed Site History, Report Export and Signal Mapping pages are retranslated immediately so Chinese mode does not fall back to English after data refresh.

v0.8.162 extends the universal Equipment Data Review with source-schema-driven column control. Every built-in App field that exists in Map Fields, plus every USER App column, is available in the same five-source review grid. Reviewers can show/hide optional columns globally, while fields that feed system matching/Analysis/validation are locked visible. New App fields appear automatically without changing the comparison engine. Equipment Data Review defaults to `All Equipment`; RMU is now just one DeviceType filter rather than a separate special review mode. Runtime bilingual switching is also hardened with an in-memory language state so Chinese ↔ English repaints immediately, including custom-painted grouped headers.

Runtime language switching is now bidirectional and immediate without restart. ADMS SLD also exposes separate `Type` and `Device Type` fields when mapped.

This release keeps the established bilingual application behavior while treating the five physical source names and source-field contracts as language-neutral engineering identifiers.

In Simplified Chinese, surrounding workflow/navigation/help text is Chinese. The five source names remain exactly `SE`, `ZENON DB`, `ZENON SLD`, `ADMS DB`, `ADMS SLD`; physical CSV/XLSX headers remain unchanged. Equipment-review workflow headings may remain localized so the customer-facing review flow stays easy to read.

v0.8.159 also reduces latency on stations with 1,000+ equipment rows by batching table painting, removing per-row QWidget checkboxes, suppressing unnecessary viewport repaints, reducing redundant cell metadata and eliminating repeated SQLite custom-field metadata reads inside the equipment-row loop.

All v0.8.156+ all-equipment five-source Review/Resolution/Comments/lifecycle behavior and v12 project data are preserved.
