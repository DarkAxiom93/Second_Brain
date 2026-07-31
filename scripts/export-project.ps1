[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [switch]$UseTestDatabase
)

$ErrorActionPreference = "Stop"
$parsedProjectId = [guid]::Empty
if (-not [guid]::TryParse($ProjectId, [ref]$parsedProjectId)) {
    throw "ProjectId must be a valid UUID."
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    throw "OutputPath is required."
}
$parent = Split-Path -Parent $OutputPath
if ([string]::IsNullOrWhiteSpace($parent)) { $parent = "." }
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw "OutputPath parent directory does not exist."
}
if (Test-Path -LiteralPath $OutputPath) {
    throw "OutputPath already exists; exports never overwrite."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
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

Push-Location $repoRoot
try {
    & $python -m app.project_export.runner --database-mode $mode --project-id $ProjectId --output $OutputPath
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
