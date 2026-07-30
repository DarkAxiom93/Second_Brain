[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.example"
$env:POSTGRES_PORT = "5433"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker is unavailable." }

Push-Location $repoRoot
try {
    & docker compose --env-file $envFile stop db
    if ($LASTEXITCODE -ne 0) { throw "Failed to stop the db service." }
    Write-Host "Database service is stopped. The container and named volume were preserved."
} finally {
    Pop-Location
}
