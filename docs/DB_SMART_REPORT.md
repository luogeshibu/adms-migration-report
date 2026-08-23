# Signal Mapping Review

This document supersedes the old DB Smart Report behavior.

As of v0.7.0, Signal Mapping Review is **calculated**, not displayed from a worksheet. The application reads `ZENON-ADMS-IOA.csv`, looks up RMU `Type` from `ADMS-SLD.csv`, and uses only `STANDARD!Type`, `STANDARD!IOA`, and `STANDARD!name` from the site's report workbook.

See `SIGNAL_MAPPING_ENGINE.md` for the calculation and failure-reason contract.
