[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"

if (-not (Get-Command "node.exe" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js was not found. Run .\scripts\frontend-setup.ps1 after installing Node.js 22.12.0 or newer."
    exit 1
}
if (-not (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)) {
    Write-Error "npm was not found. Run .\scripts\frontend-setup.ps1 after installing npm 10.0.0 or newer."
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
    Write-Error "Frontend dependencies are missing. Run .\scripts\frontend-setup.ps1."
    exit 1
}

Push-Location $frontendRoot
try {
    & npm.cmd run dev -- --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
