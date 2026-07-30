# Second Brain chat handoff

Second Brain is a local knowledge-memory API. The repository is normally at
`C:\Users\user\Desktop\second-brain` on Windows with Python 3.12 in `.venv`.
FastAPI runs on the host; PostgreSQL 16 + pgvector runs in Docker. Host database
connections use `127.0.0.1:5433`: development database `second_brain`, test
database `second_brain_test`. Obtain credentials from local example/configuration
workflow; never paste secrets.

Current Alembic head: `0009_memory_expiration`. Checkpoints 1 through 35 are
complete. Completed capabilities include:
persistence, projects, Memories, normalized sources, structured metadata,
lexical/semantic/hybrid search, optional embeddings, TXT/PDF ingestion, AI
proposal generation, human review, explicit promotion, and reusable developer
workflow documentation/scripts, advisory Memory duplicate/similarity detection,
conservative explicit-polarity contradiction detection, and explicit Memory
supersession, explicit Memory expiration, and explicit Memory quality
refinement. Endpoint categories
are health/readiness,
projects, Memories/search/embedding, sources/ingestion/proposal generation, and
proposal review/promotion.

`POST /answers` explicitly answers one trimmed question from a single bounded
active-Memory lexical, semantic, or hybrid retrieval (hybrid default), with an
optional project filter. Evidence receives deterministic M1..Mn labels and is
bounded to 2,000 characters per Memory and 12,000 characters total. Provider
output is strictly typed and capped; only validated cited Memories are returned,
in retrieval order, with separate nullable lexical and semantic scores. Empty
retrieval returns deterministic `insufficient_evidence` without resolving an
answer provider. Memory text is untrusted evidence, never instructions. The
operation commits nothing and stores no query, answer, prompt, conversation, or
history. There is no chat follow-up, agent, tool use, web access, or external
source retrieval.

Duplicate detection uses exhaustive normalized equality within the target's
project scope before the requested result limit. Similar-candidate discovery is
advisory and approximate, using bounded relevance-ranked lexical and compatible
stored-embedding pools; it never calls a provider or modifies stored data.

Contradiction detection is English-only and advisory. It recognizes only the
documented explicit negation and boolean-state pairs when the remaining
normalized proposition anchors match exactly. It reuses the same active,
same-project/null-project, bounded lexical and compatible stored-embedding
candidate pools, excludes differing non-null event times, calls no provider,
and persists nothing. Results may be non-exhaustive.

Memory supersession is a human-controlled `POST
/memories/{older_memory_id}/supersede` action whose body identifies an existing
active replacement. It requires equal nullable project scope, atomically links
the active replacement and marks the older Memory superseded, permits acyclic
chains, enforces one direct successor under deterministic row locking, and is
idempotent without timestamp writes. It never resolves contradictions
automatically or rewrites content, provenance, proposals, or embeddings.

Memory expiration is the human-controlled `POST /memories/{memory_id}/expire`
action. It locks one row, transitions only an active Memory to `expired`, uses
the request UTC time for a null or future `expires_at`, preserves an equal or
past timestamp, and is idempotent without repeat timestamp writes. No scheduler
or timestamp-passing behavior changes status automatically. Similarity keeps its
existing non-active-target behavior while filtering candidates to active rows;
contradiction detection requires active targets and candidates.

Memory quality refinement is the human-controlled `POST
/memories/{memory_id}/quality` action. It row-locks one active Memory and
updates supplied finite confidence and/or importance values in the inclusive
0.0..1.0 range. Omitted fields are preserved, complete pairs are atomic, and
equal requests return unchanged without writing. It makes no provider call,
performs no automatic scoring, and changes no ranking policy.

Retrieval quality evaluation is a developer-only, nine-case versioned harness
for lexical, semantic, and hybrid active-Memory retrieval. It directly reuses
production retrieval, uses fixed local 1536-dimensional vectors, and reports
Hit@K, Recall@K, MRR, and Precision@K separately by mode. The PowerShell 5.1
command verifies `second_brain_test`, creates fixtures inside one transaction,
rolls back every application-table write, makes no provider call, and optionally
writes JSON only to an explicit output path. Baseline checks use reviewed minimum
thresholds and never update the checked-in baseline automatically.

Read `AGENTS.md` and stable docs before work. One checkpoint at a time; preserve
exact API behavior; use the test database for integration tests; never downgrade
development, expose secrets, call paid providers without approval, delete
volumes, or commit/push without approval. Run Full verification with zero skips.

Most recently completed: Checkpoint 35, retrieval quality evaluation harness.
Scheduled expiration processing remains deferred. Continue one approved
checkpoint at a time and attach the latest checkpoint report to the new
conversation.

## Copy from PowerShell

```powershell
Get-Content .\docs\CHAT_HANDOFF.md -Raw | Set-Clipboard
```
