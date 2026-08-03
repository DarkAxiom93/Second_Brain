[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"

if (-not (Get-Command "node.exe" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js was not found. The frontend requires Node.js 22.22.0 or newer."
    exit 1
}
if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    Write-Error "npm was not found. Checkpoint 42 requires npm 10.0.0 or newer."
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "package-lock.json"))) {
    Write-Error "frontend\package-lock.json was not found."
    exit 1
}

Push-Location $frontendRoot
try {
    & npm.cmd ci
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
