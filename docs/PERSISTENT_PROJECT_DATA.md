# Persistent Project Data

The application release and the operator's project records have separate lifecycles.

- Release/source directory: replaceable.
- Site Repository: input/source data.
- Project Data: persistent application state.

## Unified site mode

For any site that must be moved to another machine, regardless of its current
review status, the Settings page provides **Prepare Transfer Package (One-time)**. It copies the live CSV/XLSX/XLSM
inputs under the site's `source_files/` directory and rewrites source links to paths
relative to that site folder. The original source repository is never deleted or
modified. `project.db` remains the authority for Comments, Checked, Review Status,
Resolution decisions and audit history.

The application organizes source CSV/XLSX/XLSM files under the site's
`source_files/` directory and generated deliverables under `reports/`.
`project.db` and `project.json` remain at the site root. Existing packages with
root-level source files are reorganized automatically when opened, without
changing the database or review records.

After this migration, the folder containing `project.db` and the source tables is
the complete site. Opening a unified site uses its database in place; it does not
create a second Project Data copy. New sites also use this in-place layout by
default. Legacy sites with an existing `project_data/workspace/<site>/project.db`
continue using the old split layout until they are migrated.

Default Windows Project Data root: `%LOCALAPPDATA%\MigrationReportTool\project_data`.

Per-site layout:

```text
project_data/
  workspace/
    1-ABH/
      project.db
      project.json
      source_files/
      snapshots/
      generated/
      reports/
        signed/
      backups/
```

`project.db` retains RMU and Signal human review state, Comments, Resolution decisions, Change Audit history, named Site History revisions, Issue / Action records, generated sign-off report metadata/snapshots/hashes and signed-copy metadata. `project.json` retains site/source mappings and project configuration.

Generated sign-off PDFs live under `reports/`. Signed/scanned copies attached from the App are copied into `reports/signed/`. Both folders are part of persistent Project Data and therefore survive application replacement/upgrades.

Future schema changes are forward-only. Before a database migration the current SQLite database is copied consistently into `backups/`; migration failure restores the pre-upgrade database.
