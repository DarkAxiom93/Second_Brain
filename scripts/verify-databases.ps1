[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project Python was not found at .venv\Scripts\python.exe." }

$env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain"
$env:TEST_DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain_test"
$code = @'
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

for variable, expected in (("DATABASE_URL", "second_brain"), ("TEST_DATABASE_URL", "second_brain_test")):
    value = os.environ[variable]
    url = make_url(value)
    if url.host != "127.0.0.1" or url.database != expected:
        raise SystemExit(f"{variable} has an unsafe host or database identity")
    engine = create_engine(value)
    try:
        with engine.connect() as connection:
            actual = connection.scalar(text("SELECT current_database()"))
    finally:
        engine.dispose()
    if actual != expected:
        raise SystemExit(f"{variable} live database identity mismatch")
    print(f"{variable}: host=127.0.0.1 port={url.port} database={expected} verified")
'@
$code | & $python -
if ($LASTEXITCODE -ne 0) { throw "Database identity verification failed." }
