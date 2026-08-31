[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("authorize", "status", "reauthorize", "revoke")]
    [string]$Action,
    [Parameter(Position = 1)]
    [string]$Reference
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project Python was not found."
}
if ($Action -eq "authorize" -and $Reference) {
    throw "Authorize does not accept a credential reference."
}
if ($Action -ne "authorize" -and -not $Reference) {
    throw "The exact credential reference is required."
}
$arguments = @("-m", "app.google_oauth.operator", $Action)
if ($Reference) { $arguments += $Reference }
Push-Location $repoRoot
try {
    & $python $arguments
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
