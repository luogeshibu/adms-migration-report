# v0.8.196 Validation

Release: `MigrationReportTool-v0.8.196-Review-Interaction-Performance`

## Scope

This release optimizes the Equipment Data Review interaction hot path without changing comparison or review business semantics.

- one canonical in-memory Equipment Review session per active site/profile
- local row hide/show for search and Review/Analysis filters
- cached equipment/review/resolution/row-index lookup
- optimistic Review Status UI with background batched SQLite persistence
- cached summary/Resolution counters
- lifecycle reads skipped for equipment with no Needs Action tracking history
- 220 ms lifecycle selection debounce
- site/source changes invalidate the session; ordinary reviewer edits keep it hot

## Automated regression

- `PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'`: **395 tests passed**
- targeted v0.8.193/v0.8.195/v0.8.196 tests: **18 passed**
- `python -m compileall -q src tests`: passed
- ZIP integrity: pending packaging check
