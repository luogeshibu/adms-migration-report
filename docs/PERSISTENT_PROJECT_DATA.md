# Persistent Project Data

The application release and the operator's project records have separate lifecycles.

- Release/source directory: replaceable.
- Site Repository: input/source data.
- Project Data: persistent application state.

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
