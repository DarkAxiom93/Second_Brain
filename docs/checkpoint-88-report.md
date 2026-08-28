# Checkpoint 88 report - OS credential-store prerequisite and secret boundary

Status: **Approved and complete after human review.**

## Outcome

Checkpoint 88 adds an application-owned exact-reference credential-store
contract, a Windows Credential Manager adapter implemented with Python stdlib
`ctypes`, an isolated deterministic fake, and a local non-echoing operator
command. Windows generic credentials use `CRED_PERSIST_LOCAL_MACHINE` in the
current user's Credential Manager, a per-user DPAPI-protected OS facility.
Normal use calls only exact `CredReadW`, `CredWriteW`, and `CredDeleteW` targets;
it never enumerates credentials.

No migration, connector account/persistence, GitHub or other network access,
public API, frontend secret entry, Tool, Agent authority, Automation authority,
external write, or Memory/import behavior was added. Checkpoint 89 was not
started.

## Preflight

- Branch `main`; initial working tree clean.
- Fetched HEAD and `origin/main` were both
  `247cc795ed9ec6afb7747a3ed7d5d2a16121c967`, ahead/behind `0/0`.
- Checkpoint 87 is contained by `origin/main`.
- Push CI run `33166692516` completed successfully for that exact commit.
- Alembic `0011_automation_persistence`; Tool Registry `agent-tools-v1`;
  Project export `second-brain-project-export` version `1`.

## Contract and operator workflow

`CredentialStore` supports only install, internal read, exact replace, exact
revoke, and content-free status. Secrets cross the boundary as mutable
`bytearray` values; `clear_secret` overwrites transient buffers. Safe exceptions
expose only `credential_missing`, `credential_store_locked`,
`credential_store_unavailable`, or `credential_store_error`, never nested OS
exception text.

References have exact format `sbcred:v1:<UUIDv4>`. They are
application-generated, non-secret, and validated before mapping to only
`SecondBrain/connector/v1/<UUID>`. Their UUID is random and contains no secret,
secret hash, checksum, fingerprint, or other derived material. Replacement
requires the exact target to exist and overwrites that same target. Revocation
deletes only that exact validated target. Per-reference locks serialize these
operations.

`scripts/manage-credential.ps1` exposes install, replace, revoke, and status.
Install/replace call Python `getpass` for interactive non-echoing entry. Neither
the wrapper nor parser accepts a secret argument. Install returns only the
opaque reference and safe status; replacement returns the same reference;
revoke returns safe status; capability diagnostics return only availability and
a stable code. No output includes secret length, prefix, suffix, checksum, hash,
or fingerprint.

## Fake store and Windows proof

`FakeCredentialStore` is instance-local, uses an injected deterministic
reference factory, copies mutable buffers, overwrites old buffers during
replacement/revocation, and supports injected missing, locked, and unavailable
failures. It never accesses the OS store.

The Windows test used one generated UUIDv4 target and proved create, exact read,
replace on the same reference, exact read of the replacement, exact delete, and
confirmed missing. Cleanup runs in `finally`, is guarded by successful creation,
and revokes only the captured exact reference. The successful missing assertion
after delete plus the `finally` guard proves no test credential remains. Neither
adapter nor test contains enumeration or unrelated deletion. On non-Windows,
the same test asserts explicit unsupported/fail-closed behavior without skip.

## Security acceptance

- **C01:** only transient buffers and the OS-protected store contain secrets;
  opaque references contain no secret. CLI/output/error and hostile nested-
  exception canaries prove redaction.
- **C02/C17:** the interface cannot express provider scope, URL, HTTP method,
  Tool, Agent, Automation, import, or other authority. Invalid references fail
  before an OS call.
- **C06:** missing, locked, unavailable, replacement, revocation, and post-delete
  lookup fail closed. Unavailable storage blocks future credential use.
- **C15:** status/diagnostics contain only availability and a safe code; there
  is no log, event, notification, trace, or raw exception integration.
- **C16:** credentials and references never enter PostgreSQL or export.
  Export schema and identity remain unchanged. Application backups contain no
  Checkpoint 88 secret; documentation notes an OS backup may independently
  include OS-protected credentials.

Credential production code imports no model, SQLAlchemy, export, or network
module. No persisted/exported application structure, API/frontend state,
diagnostic, log, backup serializer, or command output can receive the supplied
secret through this checkpoint.

## Verification evidence

Focused verification passed Ruff format/lint, strict mypy, and **65 tests with
zero skips**, covering the credential contract, fake, Windows adapter and real
round trip, operator redaction, configuration, diagnostics, and Project
export/import boundaries.

The authoritative `./scripts/verify.ps1 -Mode Full` completed successfully
before the final documentation-only edits:

- database identities, `pip check`, Ruff, format, strict mypy: passed;
- backend: **1,106 passed, zero skipped** (12 warnings);
- Alembic current and sole head: `0011_automation_persistence`;
- Alembic check: no new upgrade operations;
- frontend ESLint and TypeScript: passed;
- frontend Vitest: **128 passed in 12 files, zero skipped**;
- frontend production build and final `git diff --check`: passed.

Full was not rerun after these report/lifecycle-only documentation edits, per
the handoff instruction. A final standalone `git diff --check` was run after
the documentation edits.

## Changed paths and self-audit

- `app/credentials/__init__.py`
- `app/credentials/contract.py`
- `app/credentials/fake.py`
- `app/credentials/operator.py`
- `app/credentials/windows.py`
- `scripts/manage-credential.ps1`
- `scripts/README.md`
- `tests/test_credentials.py`
- `tests/test_credential_operator.py`
- `docs/CHECKPOINTS.md`
- `docs/ROADMAP.md`
- `docs/V1_4_ROADMAP.md`
- `docs/checkpoint-88-report.md`

All changes remain unstaged and uncommitted. Stable Alembic, Tool Registry, and
export identities are unchanged. No migration, connector/network/API/frontend,
Agent/Automation capability, external write, or reviewed-knowledge mutation was
added. Checkpoint 89 has not started. Checkpoint 88 is approved and complete.
