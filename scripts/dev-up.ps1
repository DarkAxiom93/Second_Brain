[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.example"
$env:POSTGRES_PORT = "5433"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is unavailable. Install or start Docker Desktop and retry."
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker is unavailable. Start Docker Desktop and retry." }

Push-Location $repoRoot
try {
    & docker compose --env-file $envFile up -d --no-deps db
    if ($LASTEXITCODE -ne 0) { throw "Failed to start the db service." }
    $healthy = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $status = (& docker compose --env-file $envFile ps --format json db | Out-String)
        if ($LASTEXITCODE -ne 0) { throw "Failed to inspect the db service." }
        if ($status -match '"Health"\s*:\s*"healthy"') { $healthy = $true; break }
        Start-Sleep -Seconds 2
    }
    if (-not $healthy) { throw "The db service did not become healthy." }
    & docker compose --env-file $envFile ps db
    if ($LASTEXITCODE -ne 0) { throw "Failed to report the db service state." }
    Write-Host "Database service is healthy on 127.0.0.1:5433. The named volume was preserved."
} finally {
    Pop-Location
}
