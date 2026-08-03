[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
. (Join-Path $PSScriptRoot "Invoke-IsolatedProcess.ps1")

if (-not (Get-Command "node.exe" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js was not found. The frontend requires Node.js 22.22.0 or newer."
    exit 1
}
$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npm) {
    Write-Error "npm was not found. Checkpoint 42 requires npm 10.0.0 or newer."
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendRoot "node_modules"))) {
    Write-Error "Frontend dependencies are missing. Run .\scripts\frontend-setup.ps1."
    exit 1
}

function Invoke-FrontendStage {
    param([string]$Name, [string]$Script)

    Write-Host "==> Frontend $Name"
    $result = Invoke-IsolatedProcess -FilePath $npm.Source -ArgumentList @(
        "run", $Script
    ) -WorkingDirectory $frontendRoot
    Write-ProcessResult $result
    if ($result.ExitCode -ne 0) {
        Write-Error "Frontend $Name failed with exit code $($result.ExitCode)."
        exit $result.ExitCode
    }
}

Invoke-FrontendStage "lint" "lint"
Invoke-FrontendStage "type check" "typecheck"
Invoke-FrontendStage "tests" "test"
Invoke-FrontendStage "production build" "build"
Write-Host "Frontend verification completed successfully."
exit 0
