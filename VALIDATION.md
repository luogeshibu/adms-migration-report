# v0.8.164 Validation

This release is a presentation/i18n hardening update on top of v0.8.163.

## Scope checked

- Review Versions: action button, empty state and meta table headers.
- Site History: summary counters, revision table, Issue/Action, lifecycle, RMU follow-up, audit and PDF sign-off tabs.
- Report Export: page title, explanatory copy, delivery status, report path/history labels and navigation buttons.
- Change Audit: explanatory card, empty state and audit headers.
- Signal Mapping Review: empty/loading states, summaries, actions, tooltips and runtime source/mode labels.
- Settings/first-run setup, lifecycle/action dialogs, source-mapping/column-order guidance and transient status-bar messages.
- Chinese -> English and English -> Chinese runtime switching, including refreshed dynamic labels and embedded tooltip prose.

## Language boundary preserved

Physical source names and source-data contracts remain language-neutral: `SE`, `ZENON DB`, `ZENON SLD`, `ADMS DB`, `ADMS SLD`, physical source headers, App/internal field keys and auditable table-body data are not rewritten by UI localization.

## Checks completed

- Python `compileall` over `src` and `tests`: **PASS**.
- v0.8.164 comprehensive i18n contracts: **10 passed**.
- Broader mapping/review/i18n regression selection covering build pipeline, source mapping, column visibility, global display names, module source layout, audit presentation, review states, v0.8.161 column behavior, v0.8.162 Device Type/Type semantics and v0.8.163 Field Mapping fix: **74 passed, 4 historical exact-version tests deselected**.
- Static visible-literal audit scans constructors, labels, buttons, meta headers, tooltips, status text and common dialogs. All nontechnical literal English presentation strings found by that scan have a Simplified-Chinese translation. Technical/file-filter/source identifiers are explicitly allow-listed.
- Runtime translation round-trip tests cover Site History counters, sign-off history, draft delivery state and embedded tooltip text to prevent Chinese -> English cache corruption.

The container environment does not include PySide6, so native Qt visual/mouse interaction is not executed here. The release therefore uses static presentation contracts, translation round-trip checks and Python compilation/regression tests rather than claiming a native GUI click-through test.
