[CmdletBinding()]
param(
    [switch]$BaselineCheck,
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python was not found." }
if (-not $env:TEST_DATABASE_URL) {
    $env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
}
$arguments = @("-m", "app.retrieval_evaluation.runner")
if ($BaselineCheck) { $arguments += "--baseline-check" }
if ($OutputPath) { $arguments += @("--output", $OutputPath) }
Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
