[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)][int]$Port = 8000,
    [switch]$Reload,
    [string]$DatabaseUrl = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python was not found." }
$env:DATABASE_URL = $DatabaseUrl
$check = @'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ["DATABASE_URL"])
if url.host != "127.0.0.1" or url.database != "second_brain":
    raise SystemExit("Unsafe DATABASE_URL identity; API startup refused")
engine = create_engine(os.environ["DATABASE_URL"])
try:
    with engine.connect() as connection:
        actual = connection.scalar(text("SELECT current_database()"))
finally:
    engine.dispose()
if actual != "second_brain":
    raise SystemExit("Live database identity is not second_brain; API startup refused")
print("Development database identity verified (127.0.0.1:5433/second_brain).")
'@
Push-Location $repoRoot
try {
    $check | & $python -
    if ($LASTEXITCODE -ne 0) { throw "Database verification failed; API was not started." }
    $arguments = @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", [string]$Port)
    if ($Reload) { $arguments += "--reload" }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Uvicorn exited with an error." }
} finally {
    Pop-Location
}
