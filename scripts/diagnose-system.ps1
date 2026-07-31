[CmdletBinding()]
param(
    [switch]$UseTestDatabase,
    [string]$OutputPath,
    [string]$ApiBaseUrl
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found at .venv\Scripts\python.exe."
}

$mode = "development"
$variable = "DATABASE_URL"
$defaultUrl = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
if ($UseTestDatabase) {
    $mode = "test"
    $variable = "TEST_DATABASE_URL"
    $defaultUrl = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
}
if (-not [Environment]::GetEnvironmentVariable($variable, "Process")) {
    [Environment]::SetEnvironmentVariable($variable, $defaultUrl, "Process")
}
if ($OutputPath -and (Test-Path -LiteralPath $OutputPath)) {
    throw "OutputPath already exists; overwrite is refused."
}

$arguments = @(
    "-m", "app.diagnostics.runner",
    "--database-mode", $mode,
    "--repo-root", $repoRoot
)
if ($OutputPath) { $arguments += @("--output", $OutputPath) }
if ($ApiBaseUrl) { $arguments += @("--api-base-url", $ApiBaseUrl) }

Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
