# RMU Review Color System (v0.6.7)

The RMU Data Review uses two independent visual layers so color remains understandable as the number of Analysis fields grows.

## Row status = severity

Only the actual data region (starting at Index / No. / RMU and continuing through source-data columns) receives the row status background.

| Status | Rule | Color intent |
|---|---|---|
| Pass | 0 FALSE Analysis fields | pale green |
| 1 Issue | exactly 1 FALSE field | pale yellow |
| 2 Issues | exactly 2 FALSE fields | pale orange |
| Critical / NAME | NAME is FALSE, or 3+ FALSE fields | pale red |

NAME has special priority because a name mismatch can indicate that the RMU identity/linkage itself is wrong. Therefore a row with only `NAME = FALSE` is still Critical.

## FALSE field = exact problem

The Analysis / Remarks / Comments review block remains neutral. TRUE stays neutral. A FALSE cell identifies the exact mismatch:

- NAME: red
- FEEDER: yellow
- SMART: blue
- TYPE: orange

This means a FEEDER+SMART mismatch and a FEEDER+TYPE mismatch both use the same row severity (2 Issues / orange), while the individual FALSE cells show which two fields are wrong.

## Why combination-specific colors were removed

Four Boolean Analysis fields already allow 15 non-empty mismatch combinations. Assigning a unique row color to every combination would make the legend difficult to learn and impossible to extend cleanly. Severity colors remain stable even if more Analysis fields are added later.

## Excel export

`RMU Data Review` uses the same severity and FALSE-field colors as the desktop App. The Analysis header also contains an Excel comment explaining the color rules.
