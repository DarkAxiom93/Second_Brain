[CmdletBinding()]
param(
    [ValidateSet("Quick", "Full")][string]$Mode = "Full",
    [switch]$SkipDatabase
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python was not found." }

function Invoke-Stage {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "==> $Name"
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Name failed." }
}

Push-Location $repoRoot
try {
    if ($SkipDatabase) {
        Write-Warning "PostgreSQL verification was not performed. This is insufficient for final checkpoint approval."
    } elseif ($Mode -eq "Full") {
        & (Join-Path $PSScriptRoot "verify-databases.ps1")
        if ($LASTEXITCODE -ne 0) { throw "Database verification failed." }
    }

    Invoke-Stage "pip check" @("-m", "pip", "check")
    Invoke-Stage "Ruff lint" @("-m", "ruff", "check", ".")
    Invoke-Stage "Ruff format check" @("-m", "ruff", "format", "--check", ".")
    Invoke-Stage "mypy" @("-m", "mypy", "app")

    if ($Mode -eq "Full") {
        if ($SkipDatabase) { throw "Full mode cannot run database tests with -SkipDatabase. Use Quick for documentation preflight." }
        $env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
        $env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
        Write-Host "==> complete pytest suite"
        $pytestOutput = (& $python -m pytest 2>&1 | Out-String)
        Write-Host $pytestOutput
        if ($LASTEXITCODE -ne 0) { throw "pytest failed." }
        if ($pytestOutput -match "\b[1-9][0-9]* skipped\b") { throw "pytest reported skipped tests; Full verification requires zero skips." }
        Invoke-Stage "Alembic current" @("-m", "alembic", "current")
        Invoke-Stage "Alembic heads" @("-m", "alembic", "heads")
        Invoke-Stage "Alembic check" @("-m", "alembic", "check")
    } else {
        Write-Host "==> Quick tests (tests root only; integration and migration lifecycle excluded)"
        $quickTests = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "tests") -File -Filter "test_*.py" | ForEach-Object { $_.FullName })
        if ($quickTests.Count -eq 0) { throw "No reliable Quick test selection was found." }
        & $python -m pytest @quickTests
        if ($LASTEXITCODE -ne 0) { throw "Quick tests failed." }
    }

    Write-Host "==> git diff --check"
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }
    Write-Host "$Mode verification completed successfully."
} finally {
    Pop-Location
}
