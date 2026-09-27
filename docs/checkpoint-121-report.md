# Checkpoint 121 report - Capture security and evaluation gate

Status: **Implemented; pending human review.** CP122 has not
started.

## Baseline and boundary

CP121 began from clean synchronized `main` at
`3a84ec4e20289d7f167dfefdd6dcb187406a3839`; `origin/main` was the same commit
and exact push CI run 93 was successful. The sole Alembic head was and remains
`0017_capture_items`.

This checkpoint changes only tests, test configuration, and documentation. It
adds no production capability, API, schema, migration, dependency, Capture
behavior, Source authority, Tool, Agent, Automation, Context Hub, provider,
export/import format, or frontend product behavior.

## Closed executable manifest

`tests/test_capture_security_evaluation.py` owns the ordered CAP01-CAP18
manifest. It contains exactly **44 unique mapped nodes** across the 18 threats. The
validator rejects missing, extra, renamed, empty, duplicate, non-assertive,
pytest skip/skipif/xfail, Vitest skip/todo, and recursively discovered
fixture/environment skip coverage. Every PostgreSQL node is marked
`cp121_security`; selecting one without `TEST_DATABASE_URL` fails with the
CP121-specific required-database error. Parsed and live identity must be exactly
`second_brain_test`.

The manifest itself is the canonical exact ordered mapping. Its 44 selectors are
not reused and cover runtime and static evidence where both are needed. The
remediation adds direct real-flow hostile-corpus evidence, privacy canaries,
runtime authority deltas, four conversion fault boundaries, a barrier-controlled
reassignment/conversion race, protected full-table backup/restore, and
equal-content write-once provenance. Parameterization produces **58 PostgreSQL
test instances**. Both mapped frontend nodes are part of the complete focused
Capture frontend file.

## Adversarial, PostgreSQL, and resource evidence

The bounded code-owned corpus contains eight synthetic multilingual direct and
indirect instructions, Tool/routing text, HTML/script/SVG event text,
Markdown-shaped javascript/data links, bidi/isolate and confusable text, and a
bounded multiline long string. No real Capture data or credentials are used.

Real PostgreSQL evidence covers exact Project A, Project B, and explicit
unassigned isolation; forged and swapped identifiers; sequential and concurrent
creation; the complete state/action matrix; transactional fault rollback; a
barrier-controlled conversion race; mutation and reassignment races; and stable
Capture-to-Source provenance. Existing concurrency nodes use deterministic
barriers, not timing sleeps. Conversion rollback leaves the Capture pending and
the Source/document/chunk graph empty before one clean retry.

The mapped SQL-ceiling nodes instrument successful paths and enforce create 3,
query 2, detail 2, edit 3, reassign 4, discard/restore 3, conversion/replay 10,
and resolver 3. Real SQL capture proves keyset LIMIT pagination without OFFSET,
count/facet, embedding/vector, semantic, or unbounded application iteration.
Closed-schema requests reject unsupported offset, count/facet, and
semantic/vector fields; exact 50/51 evidence proves the response maximum.

## Omission, confidentiality, and stable identities

Runtime tripwires cover DNS and sync/async HTTP during successful creation,
exact replay, conflict, and query; every count remains zero. Static dependency
and complete catalog checks cover credentials, GitHub/Google, models,
embeddings, providers, Tool Registry, fixed Agents and policy, Automations and
scheduler, Context Hub, Daily Brief, Project Watch, Curator, and Research.
Capture is absent from every authority catalog.

The exact version-1 project exporter runs with assigned and unassigned Capture
canaries. Archive names and bytes contain no Capture row, content, binding, or
identity; repeated safe export leaves both Capture rows intact. A protected
PostgreSQL custom-format `pg_dump`/`pg_restore` evidence follows the local
runbook, verifies the archive with `pg_restore --list`, and verifies
`second_brain_test` immediately before both destructive deletion and restore.
The exact Capture/Source/document/chunk graph survives recovery without
duplication. Randomized container and pytest temporary dumps are removed in a
`finally` block. No development database or persistent backup material is
touched.

Route/source inspection proves no Capture delete/purge or generic state setter.
Real FK and provenance evidence retains Project and resulting-Source delete
restrictions and exact frozen processed scope. Conversion creates no automatic
Memory, proposal, embedding, provider, Agent, Automation, or Hub state.

Stable identities remain:

- Alembic: `0017_capture_items`;
- Tool Registry: `agent-tools-v1`, exactly seven definitions;
- export: `second-brain-project-export`, version `1`.

## Verification

- Manifest/meta/adversarial selection: **16 passed**, zero skipped.
- Marked PostgreSQL CAP selection: **58 passed**, **1,476 deselected**, zero
  skipped.
- Focused Capture frontend file: **23 passed**, zero skipped.
- Exact database proof immediately before destructive evidence:
  `TEST_DATABASE_URL: host=127.0.0.1 port=5433 database=second_brain_test
  verified`; live `current_database()` also returned `second_brain_test`.

The authoritative `scripts/verify.ps1 -Mode Full` run passed database identity,
`pip check`, Ruff lint/format, and strict mypy over 217 production files. The
complete backend suite finished **1,534 passed**, zero failed and zero skipped,
including the real Credential Manager round trip and custom-format PostgreSQL
recovery. Alembic current/head/check passed at `0017_capture_items`. Frontend
ESLint, TypeScript checking, **180/180** tests, and the 90-module production Vite
build all passed. Full verification completed successfully.

The five previous full-suite timeouts were deterministic test-harness costs:
their setup
now uses synchronous controlled changes while preserving the same request and UI
assertions, and the Capture cursor test explicitly settles its deferred work.
All five complete files pass **86/86**; the complete frontend suite passes
**180/180**, zero skipped. One unrelated Answers test timed out only while the
frontend Full run deliberately overlapped the PostgreSQL gate; it passed alone,
in its complete file (**6/6**), and in the subsequent uncontented complete suite.
No product defect was found and no timeout was increased.

Final Ruff lint, Ruff format check over 525 files, and `git diff --check` pass.

## Exact changed paths

- `docs/ARCHITECTURE.md`
- `docs/checkpoint-121-report.md`
- `frontend/src/Agents.test.tsx`
- `frontend/src/Capture.test.tsx`
- `frontend/src/ConnectorAccounts.test.tsx`
- `frontend/src/Search.test.tsx`
- `frontend/src/Settings.test.tsx`
- `pyproject.toml`
- `tests/integration/conftest.py`
- `tests/integration/test_capture_api.py`
- `tests/integration/test_capture_conversion.py`
- `tests/integration/test_capture_persistence.py`
- `tests/integration/test_capture_security.py`
- `tests/integration/test_project_import.py`
- `tests/test_capture_security_adversarial.py`
- `tests/test_capture_security_evaluation.py`

Everything remains unstaged and uncommitted for human review. Nothing was
committed, pushed, or opened as a pull request. CP122 has not started.
