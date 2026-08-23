# Formal Build and Release

There is exactly one formal build/release entry point:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The Windows environment must already have been initialized with:

```bat
setup.bat
```

## Separation of responsibilities

`setup.bat` owns environment creation and dependency installation. `build.ps1` owns release production only.

`build.ps1` performs:

1. verify `.venv` exists and is Windows x64 Python 3.11–3.14;
2. verify PySide6/openpyxl/PyInstaller imports;
3. run `pip check`;
4. verify installed versions exactly match `requirements.lock.txt`;
5. run preflight validation;
6. run regression tests;
7. generate Windows/build metadata;
8. run PyInstaller;
9. run packaged EXE `--self-test`;
10. create versioned release folder, ZIP, manifest and SHA256;
11. clean disposable staging unless explicitly retained.

The build does **not** run `pip install`, does **not** create `.venv`, and does **not** call another setup script. If the environment is missing or does not match the lock file, it fails with `Run setup.bat first`.

## PowerShell execution policy

A downloaded `build.ps1` may have a Windows Internet-origin mark. The recommended command uses `Bypass` only for that PowerShell process and does not change machine/user policy.

After reviewing the script, you may alternatively run once:

```powershell
Unblock-File .\build.ps1
```

Then direct `./build.ps1` works if local policy permits it.

Every Python subprocess uses an explicit argument array, so a build cannot silently fall into the Python interactive `>>>` REPL.

## Formal artifacts

```text
release/vX.Y.Z/
├─ MigrationReportTool-vX.Y.Z-Windows-x64/
├─ MigrationReportTool-vX.Y.Z-Windows-x64.zip
├─ MigrationReportTool-vX.Y.Z-Windows-x64.manifest.json
└─ SHA256SUMS.txt
```

`build/` is disposable staging. A failed build returns a non-zero exit code and must not be treated as a formal release.
