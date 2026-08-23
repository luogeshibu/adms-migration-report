# Spreadsheet Selection (v0.6.5)

## Scope

The interaction applies to both business review grids:

- **RMU Data Review**
- **Signal Mapping Review**

## Selection behavior

| Action | Result |
|---|---|
| Click | Select one cell |
| Drag | Select one rectangular block |
| Ctrl + click / drag | Add or remove a non-contiguous cell/range |
| Shift + click | Extend from the current anchor |
| Click empty grid area | Clear selection |
| Click outside the grid | Clear selection and current-cell marker |

The implementation uses `QAbstractItemView.SelectItems` with `ExtendedSelection`. A small `SpreadsheetTableWidget` handles empty-area clearing, while the main window uses an application-level mouse event filter so clicks on non-focusable page backgrounds also clear stale table selections on Windows.

## Visual contract

Selection is intentionally **outline-only**. It does not paint a blue selection background, because business colors already encode PASS / NAME / FEEDER / SMART / TYPE mismatch states.

Double-click editing/review behavior is unchanged. Source-data columns remain read-only where applicable.
