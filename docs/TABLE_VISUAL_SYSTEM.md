# Table Visual System (v0.6.4)

The application uses one visual rule across RMU Data Review, Signal Mapping Review, Audit Log, Versions and repository tables:

- Table headers are neutral and express structure only.
- Business colors are reserved for data state.
- Comparison Analysis / Remarks / Comments remain neutral; only FALSE Analysis cells receive stronger status colors.
- Comparison row color begins at Index (No./RMU) and continues through source-data columns.
- Selection uses an outline instead of a blue fill so state colors are not obscured.

Comparison row meanings:

- pale green: all available Analysis values are consistent
- pale red: NAME mismatch
- pale yellow: FEEDER mismatch
- pale blue: SMART mismatch
- pale orange: TYPE mismatch
- pale purple: FEEDER + TYPE mismatch


## RMU severity palette (v0.6.7)

Business row colors are severity-only: Pass green, 1 Issue yellow, 2 Issues orange, Critical/NAME red. Field-specific meaning is carried only by FALSE Analysis cells: NAME red, FEEDER yellow, SMART blue, TYPE orange. No combination-specific row colors are defined.
