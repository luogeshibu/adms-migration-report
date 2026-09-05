# Signal Mapping Review Engine (v0.8.104)

## Source contract

Signal Mapping Review is calculated by the application. The legacy `DB-smart report` worksheet is **not** read.

Inputs are:

1. `ADMS-SLD.csv` — resolves the cabinet `Type` for each RMU.
2. Active application `IOA STANDARD.xlsx` — authoritative expected point list for that exact RMU Type.
3. `ZENON-ADMS-IOA.csv` — one combined source containing both the ADMS point fields and the ZENON point fields.

From `STANDARD`, only `Type`, `IOA` and `name` participate in validation.

## Calculation flow

For every RMU:

1. Resolve the RMU Type from ADMS SLD.
2. Load the complete STANDARD point list for that exact Type.
3. Pull the ADMS side from `ZENON-ADMS-IOA.csv` and align it to STANDARD.
4. Calculate **only STANDARD vs ADMS**:
   - exact expected point/name match -> `TRUE`;
   - STANDARD point missing in ADMS -> `FALSE`;
   - ADMS point outside the selected STANDARD Type -> `FALSE`;
   - name/point mismatch -> `FALSE`.
5. Pull/show the ZENON side from the same combined file after the STANDARD/ADMS alignment.
6. A ZENON-only/different point keeps the existing semantic "where is it implemented in ADMS?" lookup. That result is an **implementation hint only**. It does not create TRUE/FALSE and it is not included in STANDARD match-rate calculation.

Display order is **STANDARD -> ADMS -> ZENON -> Analysis**. The automatic `Unchecked` state is not used.

## Persistent Needs Action

Signal `Needs Action` is a site workflow state stored in `project.db`. It remains open until a reviewer explicitly changes it; source refresh does not silently remove it. The review record stores the signal category/point snapshot so older unresolved actions remain classifiable after later mapping changes.

At PDF export time, **all signal rows in the current site whose current human Review state is `NEEDS ACTION` are counted**, whether they were created earlier or in the latest validation run. Status/Cmd uses point `< 13000`; Analog uses point `>= 13000`.

## Review metadata

`Review`, `Comments` and the manual `Checked` checkbox are application-owned metadata. They are never written back into source CSV/XLSX files.
