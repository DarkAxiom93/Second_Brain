# Second Brain chat handoff

Second Brain is a local knowledge-memory API. The repository is normally at
`C:\Users\user\Desktop\second-brain` on Windows with Python 3.12 in `.venv`.
FastAPI runs on the host; PostgreSQL 16 + pgvector runs in Docker. Host database
connections use `127.0.0.1:5433`: development database `second_brain`, test
database `second_brain_test`. Obtain credentials from local example/configuration
workflow; never paste secrets.

Current Alembic head: `0008_memory_proposals`. Checkpoints 1 through 29 are
complete. Completed capabilities include:
persistence, projects, Memories, normalized sources, structured metadata,
lexical/semantic/hybrid search, optional embeddings, TXT/PDF ingestion, AI
proposal generation, human review, explicit promotion, and reusable developer
workflow documentation/scripts, advisory Memory duplicate/similarity detection,
and conservative explicit-polarity contradiction detection. Endpoint categories
are health/readiness,
projects, Memories/search/embedding, sources/ingestion/proposal generation, and
proposal review/promotion.

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

Read `AGENTS.md` and stable docs before work. One checkpoint at a time; preserve
exact API behavior; use the test database for integration tests; never downgrade
development, expose secrets, call paid providers without approval, delete
volumes, or commit/push without approval. Run Full verification with zero skips.

Most recently completed: Checkpoint 29, advisory read-only Memory contradiction
detection. The next planned Memory Quality capability is superseding, followed
by expiration, confidence, and importance work, one approved checkpoint at a
time. Attach the latest checkpoint report to the new conversation.

## Copy from PowerShell

```powershell
Get-Content .\docs\CHAT_HANDOFF.md -Raw | Set-Clipboard
```
