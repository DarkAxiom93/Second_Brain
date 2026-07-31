# Checkpoint report

Checkpoint: 39 — Versioned Project Export Bundle.

Files changed: Added typed export models, canonical serialization, project
export repository queries, streaming archive service, safe CLI runner,
PowerShell command, focused unit/PostgreSQL/script tests, stable format
documentation, and required architecture/roadmap/checkpoint/workflow updates.

Behavior: `second-brain-project-export` format version 1 creates one new
`.sbexport` bundle containing `manifest.json`, `project.json`, and all eight
required JSONL entity files, including empty files. Data rows are UUID ordered,
UTF-8/LF canonical JSON with explicit nulls and UTC timestamps. Each data file
has a row count, byte length, and SHA-256 in the manifest. The manifest is the
checksum index and does not recursively checksum itself.

API: No route or public API behavior changed.

Database: No model, table, column, index, constraint, or migration changed.
Current and sole Alembic head remains `0009_memory_expiration`.

Transactions: The command configures `REPEATABLE READ`, executes `SET
TRANSACTION READ ONLY` before identity and application queries, disables
autoflush, never flushes or commits, and rolls back/closes after export.
Repository functions issue only deterministic SELECT statements.

Scoping and integrity: Memories and runs require the exact Project ID.
Embeddings and provenance links follow exported Memories. Sources are limited
to exported Memory links and documents of target-project runs because Source
has no project ownership field. Documents and chunks follow target-project
runs. Proposals require both a target-project run and target Project ID.
Supersession, promoted-Memory, chunk, run, document, Source, MemorySource, and
embedding references are validated before final publication.

Tests: Focused unit/script coverage passes for manifest validation, canonical
JSON, timestamps, nulls, checksums, non-finite rejection, unsafe paths, empty
files, deterministic data checksums, integrity failures, temporary cleanup,
existing-output refusal, PowerShell 5.1 parsing, invalid UUID refusal, failure
propagation, and absence of dangerous switches. PostgreSQL coverage proves
field preservation, supersession, target scoping, exclusion of another Project
and unassigned Memories, manifest checksums, and test-database isolation.

PostgreSQL verification: `scripts/verify.ps1 -Mode Full` passed all 576 tests
with zero skips, pip check, Ruff lint/format, strict mypy, Alembic
current/heads/check, and `git diff --check`. Parsed and live development/test
database identities were verified as `second_brain` and `second_brain_test`.

Smoke test: Development export used existing Project
`b7fc847d-21ed-4507-aacc-834297730a75`, wrote only a unique operating-system
temporary file, opened successfully, and passed every manifest byte-length and
checksum check. Counts were Project 1, Memory 1, and zero for the other
entities. The exact temporary file was removed. The test database contained no
Project after the integration suite; a read-only missing-Project command smoke
returned exit code 1 and created no output. Creating a temporary test row solely
for a command smoke was not performed because destructive database cleanup did
not have explicit approval; the PostgreSQL integration export itself passed.

API regression: Full verification covers existing Memory, embedding,
maintenance, expiration, supersession, refinement, search, answer, evaluation,
ingestion, proposal, Source, and Project behavior.

External calls: None. No provider is imported or resolved by export and no
network/provider request occurs.

Warnings: Bundles may contain Memory and extracted text, evidence snapshots,
filenames, Source metadata, and vectors. Version 1 has no encryption and is not
safe to publish or transmit unprotected. This is not `pg_dump`; import and
restore are deferred to Checkpoint 40.

Git status: `main` matches `origin/main` at `5853269`. Only unstaged/untracked
Checkpoint 39 changes remain. Nothing was staged, committed, pushed, or
published.

Scope confirmation: Checkpoint 39 only. No API, migration, table, import,
restore, provider call, background job, schedule, cloud upload, encryption,
automatic embedding, application behavior change, staging, commit, push, PR,
or Checkpoint 40 work was added.

Omitted headings: None.
