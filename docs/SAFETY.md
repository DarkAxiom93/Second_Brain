# Safety rules

- Never print or commit secrets. Never add a real `.env` file or place an API key
  in logs, errors, reports, fixtures, or documentation.
- Never downgrade `second_brain`; never delete a database or Docker volume.
- Always verify parsed database identity and live `current_database()`.
- Never use broad or unbounded `DELETE` for smoke cleanup. Require the exact
  captured UUID and exact expected unique name, preserve all pre-existing rows,
  and delete only rows created in the current smoke run.
- Smoke cleanup must reject deletion if a Memory would be removed, ownership is
  unrelated, expected counts differ, or protected table counts change.
- External paid calls require explicit approval; automated tests use fake
  providers.
- Never force-push or stage unrelated files.

General cleanup authorization in a prompt never overrides exact database,
record, ownership, and expected-count checks. `Remove-SmokeSource.ps1` is a
narrow safety tool, not a generic deletion interface, and `-Execute` still
requires explicit human approval.
