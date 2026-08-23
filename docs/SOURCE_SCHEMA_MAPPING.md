# Source Schema Mapping

## Rule

Business logic never reads external CSV/XLSX column names directly. Every tabular source is converted to canonical fields first:

```text
CSV/XLSX -> Header Scan -> SourceSchema -> Mapping Validation -> Canonical Rows -> Review Engine
```

This prevents a renamed column from silently becoming an empty value and then being ignored by Analysis.

## Matching order

1. Site Override, when explicitly configured for the current site.
2. The first matching built-in header/alias in the source profile.
3. Missing required field -> `ERROR`, Review is blocked.
4. Missing optional field -> `WARNING`, field remains blank and is shown in Source Mapping.
5. Duplicate physical headers for the selected alias -> `AMBIGUOUS`, Review is blocked.

Matching normalizes only syntax (BOM, case, whitespace and punctuation). There is no semantic fuzzy guessing. `DEVICE -> RMU Type` works only because that mapping is explicitly maintained in the ZENON DB source profile.

## User visibility

Site Repository contains a `Schema` status column and a `Source Mapping` action. The mapping dialog shows:

- System Field
- Display Name
- Internal Key
- Required
- Actual Column
- Status
- Mapping Source (`Exact`, `Built-in Alias`, `Site Override`)

Actual-column overrides are stored in the site's `project.json`. Display Name overrides are stored in the site's `project.db`. Both are audited in `Change Audit Log`.

## Export traceability

`Import Sources` includes source file, System Field, Display Name, Actual Column, required flag, mapping type and schema status. This records both how the source was resolved and how the review column was presented.


## Mapping dialog terminology

- **System Field**: the application's built-in source field meaning.
- **Global Display Name**: application-wide presentation label used by App/Excel review headers for every site; editing it never changes the Internal Key or source file.
- **Required**: `Yes` means the Review is blocked when no unambiguous column can be resolved; `No` produces a warning and the field stays blank.
- **Actual Column**: `Auto (SS)` / `Auto (FEEDR)` means the current source header was resolved automatically. Selecting another header creates a site-specific override. Mouse-wheel selection changes are disabled to avoid accidental remapping.
- **Status = Exact**: the detected header matches the preferred built-in header after safe syntactic normalization.
- **Status = Built-in Alias**: the detected header matches another explicitly approved alias.
- **Status = Missing**: no approved header was found. Required fields block Review; optional fields do not.
- **Mapping Source**: shows whether the mapping came from built-in rules or an explicit Site Override.
