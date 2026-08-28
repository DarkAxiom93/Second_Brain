[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("install", "replace", "revoke", "status")]
    [string]$Action,
    [Parameter(Position = 1)]
    [string]$Reference
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found at .venv\Scripts\python.exe."
}
if (($Action -eq "replace" -or $Action -eq "revoke") -and -not $Reference) {
    throw "The exact credential reference is required for this action."
}
if (($Action -eq "install" -or $Action -eq "status") -and $Reference) {
    throw "This action does not accept a credential reference."
}
$arguments = @("-m", "app.credentials.operator", $Action)
if ($Reference) { $arguments += $Reference }
Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
