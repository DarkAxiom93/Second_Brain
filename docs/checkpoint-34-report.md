# Checkpoint report

Checkpoint: 34 — Evidence-Backed Memory Answers.

Files changed: Added answer schemas, provider abstraction and OpenAI Responses
API adapter, deterministic answer service, `/answers` route, scored active-only
repository retrieval, configuration, focused/unit/PostgreSQL tests, and required
documentation. Existing route-list regressions were updated for the one new
public route.

Behavior: One stateless `POST /answers` operation retrieves active Memories once
in lexical, semantic, or hybrid mode, optionally within one project, then asks a
strict provider to answer only from bounded labeled evidence. It never loads
SourceDocument or SourceChunk content and adds no agents, tools, web retrieval,
or conversation behavior.

API: Request fields are `query` (trimmed, 1–500), optional UUID `project_id`,
`search_mode` (default `hybrid`), and `limit` (default 10, range 1–20). Unknown
fields are rejected. Responses contain status, answer, mode, and selected
citations; each citation has M-label/rank, `MemoryRead`, and separate nullable
lexical/semantic scores. OpenAPI documents 422, 502, and 503 behavior.

Database: No schema change. Alembic remains `0009_memory_expiration`; current,
heads, and check pass.

Transactions: Retrieval is read-only and every completed/error path rolls back;
there is no commit. Query embeddings are transient. No application row is
created, updated, or deleted.

Tests: Focused schema/service coverage validates defaults, strict fields and
provider results, citation mapping/rejection/deduplication/order, bounded
deterministic context, prompt-injection text as evidence, and non-exposure of raw
output. PostgreSQL/API tests cover lexical, semantic, and hybrid retrieval,
compatible embeddings, project filtering, all inactive statuses, score
nullability, provider/embedding call counts, no-evidence provider bypass, and
unchanged Memory/embedding row counts. Full verification passed 533 tests with
zero skips.

PostgreSQL verification: Parsed and live identities were verified as
`second_brain` and `second_brain_test` on `127.0.0.1:5433`. Full verification
passed pip check, Ruff lint/format, mypy, pytest, Alembic current/heads/check,
and git diff check.

Final approval audit: The first complete successful Full run occurred after the
Checkpoint 34 test fixes but before documentation, smoke verification, and the
later lazy provider-resolver production-route edit. Therefore it did not, by
itself, validate the final production tree. Against the final tree, the nine
focused Checkpoint 34 unit/PostgreSQL tests passed with zero skips; direct
virtual-environment invocations of Alembic current, heads, and check each exited
0 and reported `0009_memory_expiration`, the sole identical head, and no new
upgrade operations; `git diff --check` exited 0. Because production code had
changed after the earlier successful run, one fresh Windows PowerShell 5.1 Full
run was required. That run completed with exit code 0, passing all 533 tests
with zero skips and every required verification stage on the final production
and test tree. Only this report changed afterward.

External calls: None. Tests use deterministic fake providers. The prescribed
lexical empty-result live smoke returned health `ok`, HTTP 200
`insufficient_evidence`, lexical mode, and zero citations; it resolved neither
answer nor embedding provider and created no records requiring cleanup.

Warnings: Existing Starlette/httpx and intermittent Pydantic metadata warnings
remain. After the first complete successful Full run, two later Full attempts
passed all 533 tests and every stage through Alembic heads, then failed while
Python imported `_overlapped` for Alembic check with `WinError 6` (invalid
handle); a direct retry at that time encountered the same import failure. The
final audit's direct Alembic commands and single fresh PowerShell 5.1 Full run
subsequently completed successfully. Runner inspection confirms redirected
stdin/stdout/stderr and immediate stdin closure, so stdin is not proven as the
cause. No remaining runner defect is established; the transient OS/host handle
invalidation mechanism remains uncertain. Answer evidence is capped at 2,000
characters per Memory and 12,000 characters total; provider output
configuration defaults to 1,200 tokens and the typed answer is limited to 4,000
characters. Contradictions are not resolved automatically.

Git status: Checkpoint changes remain unstaged and uncommitted for review. No
commit, push, PR, branch switch, database downgrade, destructive database
command, or volume deletion occurred.

Scope confirmation: Checkpoint 34 only. No migration, persistence, chat history,
agent framework, tool calling, external-source retrieval, automatic workflow,
staging, commit, push, PR, or Checkpoint 35 work was added.
