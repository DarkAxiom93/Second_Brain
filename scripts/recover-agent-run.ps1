[CmdletBinding()]
param([Guid]$RunId)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found at .venv\Scripts\python.exe."
}
if (-not [Environment]::GetEnvironmentVariable("DATABASE_URL", "Process")) {
    $env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
}
$arguments = @("-m", "app.agent_runs.recovery_runner")
if ($RunId) { $arguments += @("--run-id", $RunId.ToString()) }
Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
