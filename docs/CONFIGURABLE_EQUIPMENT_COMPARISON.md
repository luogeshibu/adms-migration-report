# Configurable Equipment Data Review — v0.8.178

This release changes only the **source/comparison definition** for Equipment Data Review. The downstream review workflow stays compatible with v0.8.177.

## Station configuration model

For each station, the reviewer can add any number of CSV/XLSX/XLSM source tables. Each source stores:

- editable source/module title (default: selected filename stem);
- file path;
- worksheet for Excel;
- header-row number;
- Key / Index physical column;
- physical columns hidden from presentation.

A comparison rule stores an editable logical title and, for each participating source, the physical column to compare. There is no fixed SE/ZENON/ADMS role requirement in configurable Equipment Data Review.

## Row construction

Each source is indexed using its own selected Key / Index field. Keys are trimmed and matched case-insensitively. The review table is built from the **union of keys** across all valid configured sources, so a device present in only one file is still visible.

Every physical source column is copied into the generated review row. All columns show by default; a station's Hide selection removes a column only from presentation, not from raw review data or audit projection.

## Comparison rule

For each review key and configured comparison rule:

1. Read the bound physical field from each participating source that contains that key.
2. Ignore blank values, matching the historical comparison behavior.
3. One available value => `TRUE`.
4. Two or more available values, all equal => `TRUE`.
5. Any available value differs => `FALSE`.
6. No available value => historical blank / N/A state.

A row with one or more `FALSE` rules follows the existing warning / Needs Action workflow.

## Compatibility boundary

The following are intentionally retained rather than redesigned: review statuses, Checked, lifecycle/case history, comments, resolutions, source-change audit, Excel export, sign-off PDF, report history and Signal Mapping. Existing projects continue using the legacy v0.8.177 source path until the configurable source editor is explicitly saved.
