# Derived Table Builder

v0.8.56 adds a project-local, configurable transformation layer beside the existing RMU Data Review and Signal Mapping Review engines. It does **not** replace or modify those validation algorithms.

## 1. Custom source fields

Open **Site Data Sources**, select a CSV/XLSX source, then choose **Edit Selected Table Mapping**.

The Source Mapping dialog now provides:

- **+ Add Field** — create a project-local custom field.
- **Delete Field** — remove the selected custom field.
- **Actual Column** — map the custom field to any physical header in the current source file.

Built-in System Fields remain fixed and continue to drive the existing business logic. Custom Fields are available only to the Derived Table Builder.

Custom field definitions are stored in the selected site's persistent `project.db` and survive application upgrades.

## 2. Derived output tables

Open **Site Data Sources > Derived Tables...**.

A derived table contains:

- **Table Name** — output table name, e.g. `RMU_FINAL`.
- **Base Source** — first source table.
- **Joins** — optional LEFT / INNER / FULL joins to other mapped sources.
- **Fields** — output column names and mapping/calculation expressions.
- **Preview** — calculates the table and shows up to 500 rows.
- **Export CSV / Export Excel** — writes the complete calculated result.

Derived table configurations are stored in `project.db` and are audited in Change Audit.

## 3. Source aliases

Use these aliases in expressions:

| Source | Alias |
| --- | --- |
| SE | `se` |
| ZENON DB | `zenon_db` |
| ZENON SLD | `zenon_sld` |
| ADMS DB | `adms_db` |
| ADMS SLD | `adms_sld` |
| ZENON-ADMS IOA | `ioa` |
| IOA STANDARD | `standard` |

Examples:

```text
adms_db.rmu
zenon_sld.feeder
adms_db.voltage
```

The field helper in the UI can insert a valid `source.field` reference automatically.

## 4. Calculation expressions

The expression engine is deliberately restricted and does not execute arbitrary Python code.

Supported functions include:

```text
COALESCE(a, b, c)
IF(condition, value_if_true, value_if_false)
NORMALIZE(value)
CONCAT(a, b, c)
UPPER(value)
LOWER(value)
CONTAINS(value, text)
STR(value)
INT(value)
FLOAT(value)
```

Examples:

```text
COALESCE(adms_db.smart, adms_sld.smart, se.smart)
```

```text
IF(
  NORMALIZE(zenon_sld.feeder) == NORMALIZE(adms_db.gss_fid),
  "Closed",
  "Needs Action"
)
```

```text
CONCAT(se.station, "-", adms_db.rmu)
```

Comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`), boolean `and/or/not`, and basic arithmetic are supported.

## 5. Join example

Base Source:

```text
ADMS DB
```

Join:

```text
Join Source: ZENON SLD
Join Type: LEFT
Left Expression: adms_db.rmu
Right Field: rmu
```

Output fields:

```text
RMU       = adms_db.rmu
FEEDER    = adms_db.gss_fid
Z_FEEDER  = zenon_sld.feeder
RESULT    = IF(NORMALIZE(zenon_sld.feeder) == NORMALIZE(adms_db.gss_fid), "Closed", "Needs Action")
```

## 6. Persistence and upgrade safety

SQLite schema v5 adds:

- `custom_source_fields`
- `derived_table_configs`

The existing forward-only migration system creates a consistent pre-upgrade backup before schema migration. Existing review history, comments, resolution decisions, PDF records, signed reports and source mappings are preserved.
