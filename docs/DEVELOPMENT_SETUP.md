# Windows Development Environment Setup

This project is intentionally Windows-only. There are exactly two script entry points:

- `setup.bat` — prepare or repair the local Windows Python environment.
- `build.ps1` — validate that prepared environment and create a formal release.

There is no `setup.ps1`, no build BAT wrapper, and no second release script.

## First-time setup

From `cmd.exe`, PowerShell, VS Code Terminal, or by double-clicking the file:

```bat
setup.bat
```

`setup.bat` owns the complete environment bootstrap:

1. locate supported 64-bit Python 3.11–3.14;
2. create/reuse `.venv`;
3. verify pip;
4. install the exact versions from `requirements.lock.txt`;
5. install this project in editable mode without resolving a second dependency set;
6. verify Python architecture/version, PySide6, openpyxl and the application package;
7. run `pip check` and the application `--self-test`.

No PowerShell execution policy is involved in environment setup.

### Recreate the environment

```bat
setup.bat --recreate
```

This removes `.venv` and creates it again from the lock file.

### Verify only

```bat
setup.bat --verify
```

This does not install dependencies; it verifies the existing `.venv`.

## Run from source

Activation is optional. The deterministic command is:

```powershell
.\.venv\Scripts\python.exe -m migration_report_tool
```

## Formal build

After `setup.bat` succeeds:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1` never creates a venv and never installs dependencies. A missing or stale environment fails fast with an instruction to run `setup.bat`.
