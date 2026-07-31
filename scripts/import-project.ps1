[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BundlePath,
    [switch]$UseTestDatabase,
    [switch]$Execute,
    [string]$ExpectedProjectId
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($BundlePath) -or -not (Test-Path -LiteralPath $BundlePath -PathType Leaf)) {
    throw "BundlePath must be an existing regular file."
}
if ($Execute -and [string]::IsNullOrWhiteSpace($ExpectedProjectId)) {
    throw "Execute requires ExpectedProjectId."
}
$parsedProjectId = [guid]::Empty
if (-not [string]::IsNullOrWhiteSpace($ExpectedProjectId) -and
    -not [guid]::TryParse($ExpectedProjectId, [ref]$parsedProjectId)) {
    throw "ExpectedProjectId must be a valid UUID."
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
$arguments = @("-m", "app.project_import.runner", "--database-mode", $mode, "--bundle", $BundlePath)
if ($Execute) { $arguments += "--execute" }
if (-not [string]::IsNullOrWhiteSpace($ExpectedProjectId)) {
    $arguments += @("--expected-project-id", $ExpectedProjectId)
}

Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
