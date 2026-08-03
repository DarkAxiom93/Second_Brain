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

$quickDatabaseTestNode = "tests/test_diagnostics_script.py::test_healthy_test_database_execution_and_optional_json"
$pytestTempPrefix = "second-brain-pytest-"
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd("\", "/")
$pytestRunId = [System.Guid]::NewGuid().ToString("N")
$pytestBaseTemp = Join-Path $tempRoot ($pytestTempPrefix + $pytestRunId)
$pytestBaseTemp = [System.IO.Path]::GetFullPath($pytestBaseTemp)
$expectedTempPrefix = $tempRoot + [System.IO.Path]::DirectorySeparatorChar

function Assert-PytestTempPathSafe {
    param([string]$Candidate)
    $resolvedCandidate = [System.IO.Path]::GetFullPath($Candidate)
    $leaf = Split-Path -Leaf $resolvedCandidate
    if (-not [System.IO.Path]::IsPathRooted($resolvedCandidate) -or
        -not $resolvedCandidate.StartsWith($expectedTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $leaf.StartsWith($pytestTempPrefix, [System.StringComparison]::Ordinal) -or
        $resolvedCandidate -eq $tempRoot -or
        $resolvedCandidate -eq [System.IO.Path]::GetFullPath($repoRoot) -or
        $resolvedCandidate -ne $pytestBaseTemp -or
        $leaf -ne ($pytestTempPrefix + $pytestRunId)) {
        throw "Refusing unsafe pytest temporary-directory operation."
    }
}

Assert-PytestTempPathSafe $pytestBaseTemp
try {
    $null = New-Item -ItemType Directory -Path $pytestBaseTemp -ErrorAction Stop
} catch {
    throw "Unable to prepare the isolated pytest temporary directory."
}
Write-Host "Pytest base temp: $pytestBaseTemp"

function Invoke-Stage {
    param([string]$Name, [string[]]$Arguments)
    Write-Host "==> $Name"
    $result = Invoke-IsolatedProcess -FilePath $python -ArgumentList $Arguments -WorkingDirectory $repoRoot
    Write-ProcessResult $result
    if ($result.ExitCode -ne 0) { throw "$Name failed with exit code $($result.ExitCode)." }
}

$verificationFailure = $null
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
        $pytestResult = Invoke-IsolatedProcess -FilePath $python -ArgumentList @("-m", "pytest", "--basetemp=$pytestBaseTemp") -WorkingDirectory $repoRoot
        Write-ProcessResult $pytestResult
        if ($pytestResult.ExitCode -ne 0) { throw "pytest failed with exit code $($pytestResult.ExitCode)." }
        $pytestOutput = $pytestResult.StandardOutput + $pytestResult.StandardError
        if ($pytestOutput -match "\b[1-9][0-9]* skipped\b") { throw "pytest reported skipped tests; Full verification requires zero skips." }
        Invoke-Stage "Alembic current" @("-m", "alembic", "current")
        Invoke-Stage "Alembic heads" @("-m", "alembic", "heads")
        Invoke-Stage "Alembic check" @("-m", "alembic", "check")

        Write-Host "==> frontend verification"
        $frontendResult = Invoke-IsolatedProcess -FilePath "powershell.exe" -ArgumentList @(
            "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "verify-frontend.ps1")
        ) -WorkingDirectory $repoRoot
        Write-ProcessResult $frontendResult
        if ($frontendResult.ExitCode -ne 0) {
            throw "Frontend verification failed with exit code $($frontendResult.ExitCode)."
        }
    } else {
        Write-Host "==> Quick tests (tests root only; integration and migration lifecycle excluded)"
        $quickTests = @(Get-ChildItem -LiteralPath (Join-Path $repoRoot "tests") -File -Filter "test_*.py" | ForEach-Object { $_.FullName })
        if ($quickTests.Count -eq 0) { throw "No reliable Quick test selection was found." }
        $quickArguments = @("-m", "pytest", "--basetemp=$pytestBaseTemp", "--deselect=$quickDatabaseTestNode") + $quickTests
        $quickResult = Invoke-IsolatedProcess -FilePath $python -ArgumentList $quickArguments -WorkingDirectory $repoRoot
        Write-ProcessResult $quickResult
        if ($quickResult.ExitCode -ne 0) { throw "Quick tests failed with exit code $($quickResult.ExitCode)." }
    }

    Write-Host "==> git diff --check"
    $gitResult = Invoke-IsolatedProcess -FilePath "git.exe" -ArgumentList @("diff", "--check") -WorkingDirectory $repoRoot
    Write-ProcessResult $gitResult
    if ($gitResult.ExitCode -ne 0) { throw "git diff --check failed with exit code $($gitResult.ExitCode)." }
    Write-Host "$Mode verification completed successfully."
} catch {
    $verificationFailure = $_
} finally {
    Pop-Location
    try {
        Assert-PytestTempPathSafe $pytestBaseTemp
        if (Test-Path -LiteralPath $pytestBaseTemp) {
            Remove-Item -LiteralPath $pytestBaseTemp -Recurse -Force -ErrorAction Stop
        }
    } catch {
        if ($null -eq $verificationFailure) {
            $verificationFailure = $_
        } else {
            Write-Warning "Verification failed and exact pytest temporary-directory cleanup also failed."
        }
    }
}

if ($null -ne $verificationFailure) {
    throw $verificationFailure
}
