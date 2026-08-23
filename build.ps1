[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$KeepStage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root

$Venv = Join-Path $Root '.venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
$LockFile = Join-Path $Root 'requirements.lock.txt'
$PyProject = Join-Path $Root 'pyproject.toml'
$BuildDir = Join-Path $Root 'build'
$StageRoot = Join-Path $BuildDir 'stage'
$PyInstallerWork = Join-Path $BuildDir 'pyinstaller'
$Generated = Join-Path $BuildDir 'generated'
$ReleaseRoot = Join-Path $Root 'release'
$SpecFile = Join-Path $Root 'packaging\windows\MigrationReportTool.spec'
$LogDir = Join-Path $BuildDir 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir ("build-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$TranscriptStarted = $false

function Write-Banner([string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Cyan) {
    Write-Host ('=' * 72) -ForegroundColor $Color
    Write-Host (' ' + $Text) -ForegroundColor $Color
    Write-Host ('=' * 72) -ForegroundColor $Color
}

function Assert-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label not found: $Path" }
}

function Remove-DirectorySafe([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    try { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop }
    catch {
        throw "Unable to clean '$Path'. Close MigrationReportTool.exe, Excel, Explorer preview panes, or any process using this directory. $($_.Exception.Message)"
    }
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string[]]$PythonArgs
    )
    if ($PythonArgs.Count -eq 0) { throw "$Label refused to start Python without arguments." }
    Write-Host $Label -ForegroundColor Cyan
    Write-Host ("  > {0} {1}" -f $Python, ($PythonArgs -join ' ')) -ForegroundColor DarkGray
    & $Python @PythonArgs
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE." }
}

function Assert-BuildEnvironment {
    Assert-File $LockFile 'Dependency lock file'
    Assert-File $PyProject 'pyproject.toml'
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Build environment is not initialized. Run setup.bat first. Missing: $Python"
    }

    Invoke-Python -Label '[1/10] Validating Windows build environment...' -PythonArgs @(
        '-c',
        "import struct,sys; assert sys.platform=='win32', 'Windows Python required'; assert struct.calcsize('P')*8==64, '64-bit Python required'; assert (3,11) <= sys.version_info[:2] < (3,15), 'Python 3.11-3.14 required'; import PySide6,openpyxl,PyInstaller; from migration_report_tool.version import __version__; print('Python:',sys.version.split()[0]); print('Migration Report Tool:',__version__); print('PySide6:',PySide6.__version__); print('openpyxl:',openpyxl.__version__); print('PyInstaller:',PyInstaller.__version__)"
    )
    Invoke-Python -Label '  pip dependency check' -PythonArgs @('-m','pip','check')
    Invoke-Python -Label '  locked version check' -PythonArgs @('packaging\tools\verify_locked_environment.py','--lock',$LockFile)
}

try {
    Start-Transcript -Path $Log | Out-Null
    $TranscriptStarted = $true
    Write-Banner 'Migration Report Tool - FORMAL WINDOWS RELEASE BUILD'
    Write-Host "Project root: $Root"
    Write-Host "Formal output: $ReleaseRoot"

    if (Get-Process -Name 'MigrationReportTool' -ErrorAction SilentlyContinue) {
        throw 'MigrationReportTool.exe is running. Close it before building a formal release.'
    }

    Assert-BuildEnvironment

    $Version = (& $Python -c "from migration_report_tool.version import __version__; print(__version__)").Trim()
    if (-not $Version) { throw 'Application version could not be resolved.' }
    Write-Host "Version: v$Version" -ForegroundColor Green

    Invoke-Python -Label '[2/10] Preflight validation...' -PythonArgs @('packaging\tools\preflight.py','--root',$Root)

    if (-not $SkipTests) {
        Invoke-Python -Label '[3/10] Regression tests...' -PythonArgs @('-m','unittest','discover','-s','tests','-p','test_*.py','-v')
    }
    else {
        Write-Host '[3/10] Regression tests SKIPPED by explicit developer option.' -ForegroundColor Yellow
    }

    Write-Host '[4/10] Generating build metadata...' -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $Generated | Out-Null
    Invoke-Python -Label '  Windows version resource' -PythonArgs @('packaging\tools\generate_version_info.py','--version',$Version,'--output',(Join-Path $Generated 'version_info.txt'))
    Invoke-Python -Label '  BUILD_INFO.json' -PythonArgs @('packaging\tools\write_build_info.py','--root',$Root,'--version',$Version,'--output',(Join-Path $BuildDir 'BUILD_INFO.json'))

    Write-Host '[5/10] Cleaning staging directories...' -ForegroundColor Cyan
    Remove-DirectorySafe $StageRoot
    Remove-DirectorySafe $PyInstallerWork
    New-Item -ItemType Directory -Force -Path $StageRoot,$ReleaseRoot | Out-Null

    Write-Host '[6/10] Compiling Windows x64 application...' -ForegroundColor Cyan
    Assert-File $SpecFile 'PyInstaller spec'
    & $Python -m PyInstaller --noconfirm --clean --distpath $StageRoot --workpath $PyInstallerWork $SpecFile
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller compilation failed.' }
    $StageApp = Join-Path $StageRoot 'MigrationReportTool'
    $StageExe = Join-Path $StageApp 'MigrationReportTool.exe'
    Assert-File $StageExe 'Compiled EXE'

    Write-Host '[7/10] Packaged EXE self-test...' -ForegroundColor Cyan
    & $StageExe --self-test
    if ($LASTEXITCODE -ne 0) { throw 'Packaged EXE self-test failed.' }

    Invoke-Python -Label '[8/10] Creating versioned release + ZIP + SHA256...' -PythonArgs @('packaging\tools\package_release.py','--root',$Root,'--version',$Version,'--dist',$StageApp,'--release',$ReleaseRoot)

    Write-Host '[9/10] Verifying release artifacts...' -ForegroundColor Cyan
    $ReleaseDir = Join-Path $ReleaseRoot ("v$Version")
    $Product = "MigrationReportTool-v$Version-Windows-x64"
    Assert-File (Join-Path $ReleaseDir "$Product.zip") 'Release ZIP'
    Assert-File (Join-Path $ReleaseDir 'SHA256SUMS.txt') 'SHA256SUMS'

    Write-Host '[10/10] Finalizing build workspace...' -ForegroundColor Cyan
    if (-not $KeepStage) {
        Remove-DirectorySafe $StageRoot
        Remove-DirectorySafe $PyInstallerWork
    }

    Write-Host ''
    Write-Banner 'BUILD + RELEASE SUCCESSFUL' Green
    Write-Host "Release: $ReleaseDir"
    Write-Host "ZIP:     $(Join-Path $ReleaseDir "$Product.zip")"
    Write-Host "Log:     $Log"
}
catch {
    Write-Host ''
    Write-Banner 'BUILD FAILED' Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'If the environment is missing or invalid, run setup.bat first.' -ForegroundColor Yellow
    Write-Host "Build log: $Log"
    exit 1
}
finally {
    if ($TranscriptStarted) { try { Stop-Transcript | Out-Null } catch {} }
}
