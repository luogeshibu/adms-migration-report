# Spreadsheet Selection

## Scope

The interaction applies to both business review grids:

- **RMU Data Review**
- **Signal Mapping Review**

## Selection behavior

| Action | Result |
|---|---|
| Click main grid | Select one cell |
| Drag main grid | Select one rectangular block |
| Ctrl + click / drag | Add or remove a non-contiguous cell/range |
| Shift + click | Extend from the current anchor |
| Click frozen Row Locator | Select the complete business row |
| Ctrl + click Row Locator | Add/remove non-contiguous complete rows |
| Shift + click Row Locator | Select a contiguous row range |
| Drag a scrollbar / use toolbar | Keep the current selection |
| Clear Selection | Explicitly release the current selection |

The scrolling grid always uses `QAbstractItemView.SelectItems` with `ExtendedSelection`; there is no separate Row Select mode to learn. Frozen Row Locator panes use `SelectRows` with `ExtendedSelection` and synchronize their selected rows to the corresponding scrolling grid.

## Visual contract

Selection is intentionally outline-only/transparent so business colors remain visible. Before the normal item is painted, the delegate removes Qt `State_Selected`, therefore Pass / Has Issues / Critical / FALSE / Reviewed / Closed / Needs Action backgrounds and text colors are never replaced by the platform selection palette.

For contiguous selections, only exposed perimeter edges are drawn in blue. Shared edges between adjacent selected cells/rows are omitted, so a Ctrl/Shift multi-row selection appears as one clean outer frame rather than blue stripes through every selected row. Non-contiguous selections receive one outline per independent block.

Double-click editing/review behavior is unchanged. Source-data columns remain read-only where applicable.
