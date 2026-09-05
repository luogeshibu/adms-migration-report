# Project Structure Standard — v0.8.x

The repository is a Windows desktop product with explicit domain/infrastructure/UI separation and only two operational script entry points.

```text
MigrationReportApp/
├─ setup.bat                         # Windows environment bootstrap
├─ build.ps1                         # only formal build/release entry point
├─ pyproject.toml                    # project/package metadata and dependency ranges
├─ requirements.lock.txt             # only pinned dependency lock
├─ main.py                           # source-checkout launcher
├─ src/migration_report_tool/
│  ├─ version.py                     # single application version source
│  ├─ app/                           # QApplication/bootstrap lifecycle
│  ├─ domain/
│  │  ├─ analysis/                   # consistency + severity rules
│  │  ├─ mapping/                    # Signal Mapping engine
│  │  └─ schema/                     # canonical source-schema contracts
│  ├─ services/                      # use cases/orchestration
│  ├─ infrastructure/
│  │  ├─ adapters/                   # file/DB source adapters
│  │  ├─ database/                   # SQLite persistence
│  │  ├─ export/                     # formal Excel generation
│  │  ├─ filesystem/                 # Site Repository
│  │  └─ parsers/                    # CSV/XLSX I/O
│  ├─ config/                        # table/source schema definitions
│  ├─ ui/                            # PySide6 desktop UI
│  └─ utils/                         # paths/logging/helpers
├─ tests/                            # regression/contract tests
├─ packaging/
│  ├─ windows/MigrationReportTool.spec
│  └─ tools/                         # packaging helpers; not entrypoints
├─ resources/                        # icon/splash/IOA STANDARD.xlsx
├─ docs/
├─ examples/
├─ workspace/                        # runtime site data, gitignored
├─ build/                            # disposable staging, gitignored
└─ release/                          # formal artifacts, gitignored
```

## Script ownership

- `setup.bat`: Windows Python discovery, `.venv`, locked dependency installation, editable package installation and environment verification.
- `build.ps1`: environment validation, regression tests, metadata, PyInstaller, packaged self-test and formal release packaging.

No `setup.ps1`, additional `build*.bat`, `release.bat`, `install_windows.bat`, `start_windows.bat`, `start_debug.bat` or `clean.bat` entrypoints should be added.
