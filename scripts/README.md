# Windows developer scripts

Scripts target Windows PowerShell 5.1, resolve the repository relative to their
own location, use `.venv\Scripts\python.exe`, and keep environment changes in the
script process. They never create `.env`, run migrations on startup, call a
provider, or remove the PostgreSQL volume.

## Normal workflow

```powershell
.\scripts\dev-up.ps1
.\scripts\verify-databases.ps1
.\scripts\evaluate-retrieval.ps1 -BaselineCheck
.\scripts\audit-memory-maintenance.ps1
.\scripts\diagnose-system.ps1
.\scripts\verify.ps1 -Mode Full
.\scripts\start-api.ps1 -Reload
.\scripts\dev-down.ps1
.\scripts\copy-chat-handoff.ps1
```

`verify.ps1 -Mode Quick` is the local loop. `-SkipDatabase` is allowed only with
Quick for documentation preflight and is never final approval. `start-api.ps1`
does not start Docker or migrate the database. Its optional `-DatabaseUrl`
override exists for identity/refusal testing and is never printed.

`verify.ps1` launches every external verification stage through the shared
Windows PowerShell 5.1-compatible isolated-process helper. The helper redirects
all three standard streams, closes child stdin, drains stdout and stderr
concurrently, waits for completion, preserves the real exit code and output,
and disposes the process before the next stage. Maintainers must not mix native
PowerShell pipelines or inherited host handles into this lifecycle. Run the
focused process checks with:

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive `
  -File .\scripts\tests\verify-process.ps1
```

## Narrow smoke cleanup

Capture the exact UUID and unique temporary name during the same smoke run.
Dry-run first:

```powershell
.\scripts\cleanup\Remove-SmokeSource.ps1 `
  -SourceId "00000000-0000-0000-0000-000000000000" `
  -ExpectedName "checkpoint-smoke-placeholder" `
  -ExpectedDocuments 1 -ExpectedChunks 1 -ExpectedRuns 1 -ExpectedProposals 1
```

After reviewing the checks, explicit human approval is still required before
execution:

```powershell
.\scripts\cleanup\Remove-SmokeSource.ps1 `
  -SourceId "00000000-0000-0000-0000-000000000000" `
  -ExpectedName "checkpoint-smoke-placeholder" `
  -ExpectedDocuments 1 -ExpectedChunks 1 -ExpectedRuns 1 -ExpectedProposals 1 `
  -Execute
```

The tool refuses unsafe database identity, name/count mismatches, Memory links,
and protected-row changes. It accepts no wildcard, name-only, arbitrary-table,
or unbounded-delete mode.

## Operational diagnostics

`diagnose-system.ps1` defaults to the verified `second_brain` database. Add
`-UseTestDatabase` only for `second_brain_test`, `-OutputPath` for new JSON
output, or `-ApiBaseUrl` for credential-free loopback `/health` and `/ready`
probes. It returns zero only when all required checks pass. Warnings do not
cause failure. Database work is transaction-enforced read-only; provider
configuration is inspected without provider resolution or network calls.

## Retrieval evaluation

`evaluate-retrieval.ps1` runs the deterministic, transaction-rolled-back
retrieval dataset only against `second_brain_test`. See
`docs/RETRIEVAL_EVALUATION.md` for metrics, baseline policy, and optional JSON
output.

## Memory maintenance audit

`audit-memory-maintenance.ps1` defaults to the verified `second_brain`
development database and supports `-TestDatabase`, `-DetailLimit 0..1000`, and
optional `-OutputPath`. It prints a compact summary and writes JSON only when
requested. Parsed and live identity must match before queries. The transaction
is database-enforced read-only; the command has no mutation, repair, Docker, or
provider mode.
## Project export

`export-project.ps1` creates a new, private `.sbexport` package for one Project.
It refuses invalid UUIDs, unsafe database identity, missing parent directories,
and existing output files. Add `-UseTestDatabase` only for the verified
`second_brain_test` database. See `docs/PROJECT_EXPORT_FORMAT.md`.
# Project import

Validate a private version-1 Project bundle and the development target without
writing:

```powershell
.\scripts\import-project.ps1 -BundlePath C:\backup\project.sbexport
```

Use `-UseTestDatabase` only for `second_brain_test`. A restore additionally
requires `-Execute -ExpectedProjectId <manifest-uuid>`. Import rejects every
conflict and commits the complete graph once or rolls it all back.
