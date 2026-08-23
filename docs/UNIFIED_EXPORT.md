# Unified Review Export (v0.6.7)

The formal site workbook contains exactly five sheets:

1. `RMU Data Review`
2. `Signal Mapping Review`
3. `STANDARD`
4. `Import Sources`
5. `Change Audit Log`

## Export ownership rule

`RMU Data Review` and `Signal Mapping Review` are **generated from the App review models and App layout**. They are not renamed copies of the customer `DATA` / `DB-smart report` worksheets.

The generated review sheets use the same business structure shown in the desktop application:

- neutral two-level grouped headers;
- RMU review order: `Analysis -> Remarks -> Comments -> Index -> source groups`;
- signal review order: `Review -> RMU -> ZENON -> ADMS -> STANDARD DATABASE I/O list -> Analysis -> Comparison Summary`;
- App status colors and FALSE-cell emphasis;
- App review/comments data from SQLite.

`STANDARD` is copied from the application-owned `resources/templates/IOA STANDARD.xlsx`. Site REPORT workbooks are not read. The bundled worksheet is preserved as the reference sheet in the formal five-sheet export.

`Import Sources` and `Change Audit Log` are application-generated traceability sheets.
