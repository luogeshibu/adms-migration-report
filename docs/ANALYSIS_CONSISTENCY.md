# Analysis Consistency Standard — v0.5.3

The DATA `Analysis` group (`NAME / FEEDER / SMART / TYPE`) uses a shared consistency rule.

## Decision rule

For each field, values are collected from the applicable sources: SE, ZENON DB, ZENON SLD XML, ADMS DB and ADMS SLD.

1. Blank values do not participate.
2. If every source is blank, Analysis is blank.
3. If exactly one source has a value, Analysis is `TRUE`.
4. If two or more sources have values, Analysis is `TRUE` only when every normalized value is the same.
5. Any conflicting non-blank value produces `FALSE`.

## Field normalization

- **NAME**: RMU/cabinet identifier, case-normalized.
- **FEEDER**: site-relative feeder normalization. For site `ABN2`, `ABN2-03`, `JED-NTH-ABN2-03` and `JED NTH-ABN2-3` normalize to `ABN2-3`.
- **SMART**: `SMART`, `SMR`, `YES`, `TRUE`, `1`, and SE values such as `SMART NOP HT` normalize to `SMART`; `NORMAL`, `NO`, `FALSE`, `0`, etc. normalize to `NORMAL`.
- **TYPE**: cabinet type such as `2L1T` / `3L1T`. Current ZENON DB `DEVICE` is treated as cabinet type. SE `EQUIP. TYPE` is not used as cabinet type because it represents SMART/NORMAL equipment classification in the current SE format.

The current ZENON SLD XML schema has no explicit SMART field, so SMART is not inferred from `LinkName`; it remains blank and is ignored unless an explicit SMART field is added later.

## v0.7.0 additional checks

### IP
`IP` compares the Driver info IP with the ADMS Channel IP. Blank values are ignored by the same available-value rule. IP/CIDR text is normalized before comparison. A mismatch remains visible both as a FALSE-cell highlight and as a detailed tooltip/Remarks reason.

### LINK
`LINK` is not a cross-source consistency comparison. It reads the ADMS-SLD association field for the RMU directly. A true-like value or non-empty association identifier is TRUE; a blank/false-like LINK on an existing ADMS-SLD RMU row is FALSE. If the entire ADMS-SLD RMU row is missing, LINK is N/A/blank so a missing source is not double-counted as an association failure.

## v0.7.1 column-layout migration

The Analysis model contains six visible checks: NAME, FEEDER, SMART, TYPE, IP and LINK.
When upgrading from a build that saved a four-column Analysis layout, the application automatically enables IP and LINK once.  Subsequent manual hide/show choices are preserved.


## Feeder normalization rules

Feeder comparison is site-relative and uses explicit business normalization. Region prefixes such as `JED-NTH` are ignored once the selected site token is found. Numeric zero padding is ignored (`ABH-03` = `ABH-3`). For ABH, the confirmed ADMS encoding `AH3xx` is decoded to feeder `xx`, so `JED-NTH-ABH-AH303` = `ABH-03` and `JED-NTH-ABH-AH308` = `ABH-08`. Unknown encodings are never guessed; they remain visible as mismatches.

The old ADMS Channel source-level `Analysis` column has been removed. IP consistency is represented only by the main Analysis `IP` field.
