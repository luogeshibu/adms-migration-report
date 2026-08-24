# ADMS Migration Report Tool

Professional Windows desktop review tool for SE / ZENON / ADMS migration verification.

## Main review modules

- **RMU Data Review** — automatic NAME / FEEDER / SMART / TYPE / IP / LINK validation plus structured per-issue Resolution decisions. Every FALSE Analysis field requires one explicit decision; Review is derived as `Unreviewed`, `Reviewed`, or `Needs Action`.
- **Signal Mapping Review** — automatic Matched / Mismatched / Unchecked validation from `ZENON-ADMS-IOA.csv`, `ADMS-SLD.csv` and the active application `IOA STANDARD.xlsx`, with independent human Review.
  `ADMS/STANDARD` is TRUE when normalized ADMS signal name + ADMS DOT number match STANDARD name + IOA. RMU Type is supporting context/fallback rather than a mandatory TRUE condition.
- **Project Overview** — formal migration workflow (`Data Sources -> Validation -> Human Review -> Migration Report`), RMU/Signal KPIs, review progress and delivery readiness.
  Project Overview tracks Human Review by business object: one affected RMU and one mismatched Signal. Inside RMU Data Review, each FALSE field still requires its own structured Resolution decision. Pass/Matched records do not require review by default; Unchecked signals are Validation Coverage gaps and block formal export.
- **Site Data Sources** — repository-first source discovery, fingerprints/snapshots, module dependency tables and explicit Source Schema Mapping.

## Source schema safety

Every CSV/XLSX source is resolved by column name through a maintained SourceSchema profile. Business logic receives canonical fields only. Required columns that cannot be resolved are errors; optional missing columns are warnings. There is no semantic fuzzy guessing. Confirmed site-specific names can be stored as audited overrides from **Site Repository -> Source Mapping**.

## Windows environment setup

First time, or after intentionally changing the lock file:

```bat
setup.bat
```

Clean environment rebuild:

```bat
setup.bat --recreate
```

Verify existing environment only:

```bat
setup.bat --verify
```

`setup.bat` is the only environment bootstrap. There is no `setup.ps1`.

## Development run

```powershell
.\.venv\Scripts\python.exe -m migration_report_tool
```

## Formal Windows build

After setup succeeds:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` validates the existing environment but never installs it. It runs tests, PyInstaller, EXE self-test and creates formal artifacts under `release\vX.Y.Z\`.

## Formal Excel export

Exactly five sheets:

1. RMU Data Review
2. Signal Mapping Review
3. STANDARD
4. Import Sources
5. Change Audit Log

The first two are generated from the App model. `STANDARD` is copied from the currently active application reference. `Import Sources` includes canonical-to-actual column mapping traceability. The active STANDARD can be replaced from Settings or Signal Mapping Review after Type / IOA / name schema validation.

See `docs/ARCHITECTURE.md`, `docs/PROJECT_STRUCTURE.md`, `docs/SOURCE_SCHEMA_MAPPING.md`, `docs/DEVELOPMENT_SETUP.md`, and `docs/BUILD_AND_RELEASE.md`.


## RMU review workflow

Select one or more RMU rows and click **Set Review**. The manual state is stored independently from the automatic data result:

- `UNREVIEWED` — not yet signed off by a reviewer.
- `REVIEWED` — reviewer has checked the row.
- `NEEDS ACTION` — reviewer has checked the row and wants follow-up.

The top summary keeps automatic `MATCHED / WARNING / FAILED` separate from manual review state.
