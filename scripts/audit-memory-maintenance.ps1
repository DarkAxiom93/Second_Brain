[CmdletBinding()]
param(
    [switch]$TestDatabase,
    [ValidateRange(0, 1000)]
    [int]$DetailLimit = 100,
    [string]$OutputPath,
    [string]$DatabaseUrl
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python was not found at .venv\Scripts\python.exe."
}

$mode = "development"
$variable = "DATABASE_URL"
$defaultUrl = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
if ($TestDatabase) {
    $mode = "test"
    $variable = "TEST_DATABASE_URL"
    $defaultUrl = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
}
if ($DatabaseUrl) {
    [Environment]::SetEnvironmentVariable($variable, $DatabaseUrl, "Process")
} elseif (-not [Environment]::GetEnvironmentVariable($variable, "Process")) {
    [Environment]::SetEnvironmentVariable($variable, $defaultUrl, "Process")
}

$arguments = @(
    "-m", "app.memory_maintenance.runner",
    "--database-mode", $mode,
    "--detail-limit", [string]$DetailLimit
)
if ($OutputPath) { $arguments += @("--output", $OutputPath) }

Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
