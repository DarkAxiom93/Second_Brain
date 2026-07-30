# Second Brain chat handoff

Second Brain is a local knowledge-memory API. The repository is normally at
`C:\Users\user\Desktop\second-brain` on Windows with Python 3.12 in `.venv`.
FastAPI runs on the host; PostgreSQL 16 + pgvector runs in Docker. Host database
connections use `127.0.0.1:5433`: development database `second_brain`, test
database `second_brain_test`. Obtain credentials from local example/configuration
workflow; never paste secrets.

Current Alembic head: `0008_memory_proposals`. Checkpoints 1 through 28 are
complete. Completed capabilities include:
persistence, projects, Memories, normalized sources, structured metadata,
lexical/semantic/hybrid search, optional embeddings, TXT/PDF ingestion, AI
proposal generation, human review, explicit promotion, and reusable developer
workflow documentation/scripts, and advisory Memory duplicate/similarity
detection. Endpoint categories are health/readiness,
projects, Memories/search/embedding, sources/ingestion/proposal generation, and
proposal review/promotion.

Duplicate detection uses exhaustive normalized equality within the target's
project scope before the requested result limit. Similar-candidate discovery is
advisory and approximate, using bounded relevance-ranked lexical and compatible
stored-embedding pools; it never calls a provider or modifies stored data.

Read `AGENTS.md` and stable docs before work. One checkpoint at a time; preserve
exact API behavior; use the test database for integration tests; never downgrade
development, expose secrets, call paid providers without approval, delete
volumes, or commit/push without approval. Run Full verification with zero skips.

Most recently completed: Checkpoint 28, read-only duplicate and similarity
detection. The next planned Memory Quality capability is contradiction
detection, followed by superseding, expiration, confidence, and importance
work, one approved checkpoint at a time. Attach the latest checkpoint report to
the new conversation.

## Copy from PowerShell

```powershell
Get-Content .\docs\CHAT_HANDOFF.md -Raw | Set-Clipboard
```
