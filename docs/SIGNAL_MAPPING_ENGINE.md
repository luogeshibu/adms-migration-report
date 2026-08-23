# Signal Mapping Review Engine (v0.7.0)

## Source contract

Signal Mapping Review is now calculated by the application. The legacy `DB-smart report` / `DB-smsrt report` worksheet is **not** read.

Inputs are:

1. `ZENON-ADMS-IOA.csv` — row-level Zenon/ADMS signal mapping source.
2. `ADMS-SLD.csv` — provides the RMU cabinet `Type` for each `RMU_NO`.
3. `resources/templates/IOA STANDARD.xlsx` — application-owned STANDARD reference; it is not read from Site Repository.

From `STANDARD`, only the columns named `Type`, `IOA` and `name` are consumed. All other worksheets and columns are ignored by the calculation engine.

## Calculation flow

For each IOA row:

1. Read `RMU_NO`, Zenon fields and ADMS fields from `ZENON-ADMS-IOA.csv`.
2. Find the same RMU in `ADMS-SLD.csv` and obtain its cabinet `Type`.
3. Use `(Type, ADMS_DOT_NO)` as the STANDARD lookup key.
4. Fill the App `Signal_name` and `DOT_NO` fields from STANDARD `name` and `IOA`.
5. Normalize the ADMS signal name using the established migration-report comparison rules and compare it with STANDARD `name`; the point number must also match.
6. Set `ADMS/STANDARD` to TRUE/FALSE and preserve a detailed reason tooltip.

If the RMU type is missing, the ADMS point is blank, the STANDARD key is not found, or the signal name differs, the row is FALSE and the reason states exactly why.

## Review metadata

`Review` and `Comments` remain application-owned metadata stored in the site `project.db`. They are not written back into source CSV/XLSX files.

## Export

The formal workbook contains the App-generated `Signal Mapping Review` sheet plus the source workbook's `STANDARD` sheet. No legacy DB-smart worksheet is required or exported.
