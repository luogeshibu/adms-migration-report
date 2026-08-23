# Comparison Review Workspace

Version 0.6.4 changes the **desktop Comparison view only**. The formal Excel DATA sheet remains in the customer A:BB order.

## Review-first order

The desktop grid begins with `No.`, `RMU`, the four Analysis fields, `Remarks`, and `Comments`, followed by the source groups.

## Column visibility

Use **Columns** to show/hide whole groups or individual fields. `No.` and `RMU` remain visible. Presets include Review View, Full View, and Hide Source Details. The selection is persisted with Qt application settings.

## Analysis filter

The Analysis selector can show passed rows, any mismatch, or specific NAME / FEEDER / SMART / TYPE mismatches.

## Review colors

Row background priority is: NAME mismatch (red), FEEDER+TYPE mismatch (purple), TYPE mismatch (orange), FEEDER mismatch (yellow), SMART mismatch (blue), no mismatch (green). Analysis cells also carry their own TRUE/FALSE colors. Hover an Analysis cell to see the normalized values used by the consistency rule.

## v0.6.4 color policy

The review block (`Analysis`, `Remarks`, `Comments`) remains neutral so review text is easy to read. Only `FALSE` Analysis cells receive field-specific emphasis. Row-level issue colors begin at `No.` / `RMU` and continue across all source-data columns.

- Pass: pale green
- NAME mismatch: pale red
- FEEDER mismatch: pale yellow
- SMART mismatch: pale blue
- TYPE mismatch: pale orange
- FEEDER + TYPE mismatch: pale purple



## v0.6.7 severity color contract

Row color communicates **severity**, not a specific field combination:

- Pass: pale green (0 FALSE Analysis fields)
- 1 Issue: pale yellow (exactly 1 FALSE)
- 2 Issues: pale orange (exactly 2 FALSE)
- Critical / NAME: pale red (NAME is FALSE, or 3+ Analysis fields are FALSE)

The Analysis block stays neutral. Only FALSE cells identify the exact problem:
NAME red, FEEDER yellow, SMART blue, TYPE orange. This replaces the old special FEEDER+TYPE purple row rule and scales to any future combination.


## Structured RMU Resolution (v0.8.22+)

RMU free-form Comments are no longer part of the formal review workflow. Each active FALSE Analysis field requires exactly one structured Resolution decision. Cross-source mismatches can select one authoritative source/value; LINK uses action decisions. Review remains Unreviewed until every active issue has a decision, becomes Needs Action when any decision requires correction, and becomes Reviewed when all active issues are resolved without Needs Action. Re-validation invalidates stale decisions when their issue fingerprint changes while preserving Audit history.
