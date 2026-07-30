# Windows developer scripts

Scripts target Windows PowerShell 5.1, resolve the repository relative to their
own location, use `.venv\Scripts\python.exe`, and keep environment changes in the
script process. They never create `.env`, run migrations on startup, call a
provider, or remove the PostgreSQL volume.

## Normal workflow

```powershell
.\scripts\dev-up.ps1
.\scripts\verify-databases.ps1
.\scripts\verify.ps1 -Mode Full
.\scripts\start-api.ps1 -Reload
.\scripts\dev-down.ps1
.\scripts\copy-chat-handoff.ps1
```

`verify.ps1 -Mode Quick` is the local loop. `-SkipDatabase` is allowed only with
Quick for documentation preflight and is never final approval. `start-api.ps1`
does not start Docker or migrate the database. Its optional `-DatabaseUrl`
override exists for identity/refusal testing and is never printed.

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
