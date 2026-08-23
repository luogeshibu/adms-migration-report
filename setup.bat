@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%CD%"
set "VENV=%ROOT%\.venv"
set "VENV_PY=%VENV%\Scripts\python.exe"
set "LOCK_FILE=%ROOT%\requirements.lock.txt"
set "PYPROJECT=%ROOT%\pyproject.toml"
set "MODE=setup"
set "BOOTSTRAP_EXE="
set "BOOTSTRAP_SELECTOR="
set "BOOTSTRAP_DISPLAY="

if "%~1"=="" goto :args_ok
if /I "%~1"=="--recreate" (
    set "MODE=recreate"
    goto :args_ok
)
if /I "%~1"=="--verify" (
    set "MODE=verify"
    goto :args_ok
)
goto :usage

:args_ok
if not "%~2"=="" goto :usage

call :banner "Migration Report Tool - WINDOWS ENVIRONMENT SETUP"
echo Project root: %ROOT%
echo.

if not exist "%LOCK_FILE%" (
    echo ERROR: requirements.lock.txt was not found.
    exit /b 1
)
if not exist "%PYPROJECT%" (
    echo ERROR: pyproject.toml was not found.
    exit /b 1
)

if /I "%MODE%"=="recreate" (
    if exist "%VENV%" (
        echo [1/5] Removing existing .venv...
        rmdir /s /q "%VENV%"
        if exist "%VENV%" (
            echo ERROR: Unable to remove .venv. Close Python, VS Code terminals, or processes using it.
            exit /b 1
        )
    )
)

if /I "%MODE%"=="verify" goto :verify_only

if exist "%VENV_PY%" goto :reuse_venv

echo [1/5] Locating 64-bit Python 3.11-3.14...
call :find_python
if errorlevel 1 exit /b 1

echo [2/5] Creating virtual environment...
echo   ^> %BOOTSTRAP_DISPLAY% -m venv "%VENV%"
call :run_bootstrap -m venv "%VENV%"
if errorlevel 1 (
    echo ERROR: Virtual environment creation failed.
    exit /b 1
)
goto :venv_ready

:reuse_venv
echo [1/5] Existing .venv detected.
echo [2/5] Reusing virtual environment.

:venv_ready
if not exist "%VENV_PY%" (
    echo ERROR: Virtual-environment Python was not created: %VENV_PY%
    exit /b 1
)

echo [3/5] Installing locked dependencies...
echo   ^> "%VENV_PY%" -m pip install -r requirements.lock.txt
"%VENV_PY%" -m pip --version
if errorlevel 1 (
    echo ERROR: pip is unavailable inside .venv.
    exit /b 1
)
"%VENV_PY%" -m pip install --disable-pip-version-check -r "%LOCK_FILE%"
if errorlevel 1 (
    echo ERROR: Locked dependency installation failed.
    exit /b 1
)

echo [4/5] Installing application package in editable mode...
echo   ^> "%VENV_PY%" -m pip install -e . --no-deps
"%VENV_PY%" -m pip install --disable-pip-version-check -e "%ROOT%" --no-deps
if errorlevel 1 (
    echo ERROR: Application package installation failed.
    exit /b 1
)

echo [5/5] Verifying environment...
call :verify_environment
if errorlevel 1 exit /b 1

echo.
call :banner "ENVIRONMENT READY"
echo Run source application:
echo   .\.venv\Scripts\python.exe -m migration_report_tool
echo.
echo Build formal Windows release:
echo   powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
exit /b 0

:verify_only
if not exist "%VENV_PY%" (
    echo ERROR: .venv does not exist. Run setup.bat first.
    exit /b 1
)
echo [VERIFY] Verifying existing environment...
call :verify_environment
if errorlevel 1 exit /b 1
echo.
call :banner "ENVIRONMENT READY"
exit /b 0

:verify_environment
"%VENV_PY%" -c "import struct,sys; assert sys.platform=='win32', 'Windows Python required'; assert struct.calcsize('P')*8==64, '64-bit Python required'; assert (3,11) <= sys.version_info[:2] < (3,15), 'Python 3.11-3.14 required'; import PySide6,openpyxl; from migration_report_tool.version import __version__; print('Python:',sys.version.split()[0]); print('Migration Report Tool:',__version__); print('PySide6:',PySide6.__version__); print('openpyxl:',openpyxl.__version__)"
if errorlevel 1 (
    echo ERROR: Environment verification failed.
    exit /b 1
)
"%VENV_PY%" -m pip check
if errorlevel 1 (
    echo ERROR: pip dependency check failed.
    exit /b 1
)
"%VENV_PY%" -m migration_report_tool --self-test
if errorlevel 1 (
    echo ERROR: Application self-test failed.
    exit /b 1
)
exit /b 0

:find_python
set "BOOTSTRAP_EXE="
set "BOOTSTRAP_SELECTOR="
set "BOOTSTRAP_DISPLAY="

for /f "delims=" %%P in ('where py.exe 2^>nul') do if not defined BOOTSTRAP_EXE set "BOOTSTRAP_EXE=%%P"
if defined BOOTSTRAP_EXE (
    "%BOOTSTRAP_EXE%" -3.14 -c "import struct,sys; assert struct.calcsize('P')*8==64; assert (3,11) <= sys.version_info[:2] < (3,15)" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_SELECTOR=-3.14"
        set "BOOTSTRAP_DISPLAY=py -3.14"
        goto :python_found
    )

    "%BOOTSTRAP_EXE%" -3 -c "import struct,sys; assert struct.calcsize('P')*8==64; assert (3,11) <= sys.version_info[:2] < (3,15)" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_SELECTOR=-3"
        set "BOOTSTRAP_DISPLAY=py -3"
        goto :python_found
    )
)

set "BOOTSTRAP_EXE="
for /f "delims=" %%P in ('where python.exe 2^>nul') do if not defined BOOTSTRAP_EXE set "BOOTSTRAP_EXE=%%P"
if defined BOOTSTRAP_EXE (
    "%BOOTSTRAP_EXE%" -c "import struct,sys; assert struct.calcsize('P')*8==64; assert (3,11) <= sys.version_info[:2] < (3,15)" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_SELECTOR="
        set "BOOTSTRAP_DISPLAY=python"
        goto :python_found
    )
)

echo ERROR: 64-bit Python 3.11-3.14 was not found.
echo Install Python x64, ensure py.exe or python.exe is available, then run setup.bat again.
exit /b 1

:python_found
echo   Selected: %BOOTSTRAP_DISPLAY%
exit /b 0

:run_bootstrap
if not defined BOOTSTRAP_EXE (
    echo ERROR: Internal setup error: bootstrap Python executable is empty.
    exit /b 1
)
if defined BOOTSTRAP_SELECTOR (
    "%BOOTSTRAP_EXE%" %BOOTSTRAP_SELECTOR% %*
) else (
    "%BOOTSTRAP_EXE%" %*
)
exit /b %ERRORLEVEL%

:banner
echo ========================================================================
echo  %~1
echo ========================================================================
exit /b 0

:usage
echo Usage:
echo   setup.bat              Initialize/update the Windows environment
echo   setup.bat --recreate   Recreate .venv from scratch
echo   setup.bat --verify     Verify the existing .venv only
exit /b 2
