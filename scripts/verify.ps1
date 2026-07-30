[CmdletBinding()]
param(
    [ValidateSet("Quick", "Full")][string]$Mode = "Full",
    [switch]$SkipDatabase
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python was not found." }
. (Join-Path $PSScriptRoot "Invoke-IsolatedProcess.ps1")

function Invoke-Stage {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "==> $Name"
    $result = Invoke-IsolatedProcess -FilePath $python -ArgumentList $Arguments -WorkingDirectory $repoRoot
    Write-ProcessResult $result
    if ($result.ExitCode -ne 0) { throw "$Name failed with exit code $($result.ExitCode)." }
}

Push-Location $repoRoot
try {
    if ($SkipDatabase) {
        Write-Warning "PostgreSQL verification was not performed. This is insufficient for final checkpoint approval."
    } elseif ($Mode -eq "Full") {
        $databaseResult = Invoke-IsolatedProcess -FilePath "powershell.exe" -ArgumentList @(
            "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "verify-databases.ps1")
        ) -WorkingDirectory $repoRoot
        Write-ProcessResult $databaseResult
        if ($databaseResult.ExitCode -ne 0) { throw "Database verification failed with exit code $($databaseResult.ExitCode)." }
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
        $pytestResult = Invoke-IsolatedProcess -FilePath $python -ArgumentList @("-m", "pytest") -WorkingDirectory $repoRoot
        Write-ProcessResult $pytestResult
        if ($pytestResult.ExitCode -ne 0) { throw "pytest failed with exit code $($pytestResult.ExitCode)." }
        $pytestOutput = $pytestResult.StandardOutput + $pytestResult.StandardError
        if ($pytestOutput -match "\b[1-9][0-9]* skipped\b") { throw "pytest reported skipped tests; Full verification requires zero skips." }
        Invoke-Stage "Alembic current" @("-m", "alembic", "current")
        Invoke-Stage "Alembic heads" @("-m", "alembic", "heads")
        Invoke-Stage "Alembic check" @("-m", "alembic", "check")
    } else {
        Write-Host "==> Quick tests (tests root only; integration and migration lifecycle excluded)"
        $quickTests = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "tests") -File -Filter "test_*.py" | ForEach-Object { $_.FullName })
        if ($quickTests.Count -eq 0) { throw "No reliable Quick test selection was found." }
        $quickResult = Invoke-IsolatedProcess -FilePath $python -ArgumentList (@("-m", "pytest") + $quickTests) -WorkingDirectory $repoRoot
        Write-ProcessResult $quickResult
        if ($quickResult.ExitCode -ne 0) { throw "Quick tests failed with exit code $($quickResult.ExitCode)." }
    }

    Write-Host "==> git diff --check"
    $gitResult = Invoke-IsolatedProcess -FilePath "git.exe" -ArgumentList @("diff", "--check") -WorkingDirectory $repoRoot
    Write-ProcessResult $gitResult
    if ($gitResult.ExitCode -ne 0) { throw "git diff --check failed with exit code $($gitResult.ExitCode)." }
    Write-Host "$Mode verification completed successfully."
} finally {
    Pop-Location
}
