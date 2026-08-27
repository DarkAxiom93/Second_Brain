# Checkpoints

Hashes and migration heads below come from the committed linear Git and Alembic
history. A dash means Alembic had not yet been introduced.

| # | Purpose | Status | Alembic head | Commit |
|---:|---|---|---|---|
| 1 | Repository foundation | Complete | - | `72a7201` |
| 2 | Phase 1 foundation completion | Complete | - | `f963bfb` |
| 3 | FastAPI health endpoint | Complete | - | `8ec035c` |
| 4 | PostgreSQL readiness and Alembic baseline | Complete | `0001_enable_pgvector` | `c021179` |
| 5 | Project and Memory persistence | Complete | `0002_projects_memories` | `75a80cb` |
| 6 | Project API | Complete | `0002_projects_memories` | `6438055` |
| 7 | Memory creation API | Complete | `0002_projects_memories` | `99ec5b0` |
| 8 | Memory retrieval API | Complete | `0002_projects_memories` | `c2f592a` |
| 9 | Normalized Memory sources | Complete | `0003_sources` | `9f61436` |
| 10 | Source creation and Memory linking | Complete | `0003_sources` | `51083b1` |
| 11 | Repository checkpoint | Complete | `0003_sources` | `70500f5` |
| 12 | Structured Memory metadata | Complete | `0004_memory_metadata` | `25f43ce` |
| 13 | Expose structured metadata | Complete | `0004_memory_metadata` | `210d47c` |
| 14 | Structured Memory filtering | Complete | `0004_memory_metadata` | `b767a23` |
| 15 | PostgreSQL lexical search | Complete | `0005_memory_search` | `8138493` |
| 16 | Memory embedding persistence | Complete | `0006_memory_embeddings` | `87a0eb1` |
| 17 | Explicit embedding generation | Complete | `0006_memory_embeddings` | `b97ca75` |
| 18 | Semantic search | Complete | `0006_memory_embeddings` | `f0f5b9c` |
| 19 | Hybrid RRF search | Complete | `0006_memory_embeddings` | `270f129` |
| 20 | Source document persistence | Complete | `0007_source_documents` | `2292910` |
| 21 | Plain-text ingestion | Complete | `0007_source_documents` | `d911f78` |
| 22 | TXT/PDF ingestion | Complete | `0007_source_documents` | `70a6e47` |
| 23 | Reviewable proposal persistence | Complete | `0008_memory_proposals` | `e25eb4` |
| 24 | AI proposal generation | Complete | `0008_memory_proposals` | `66690b2` |
| 25 | Human proposal review | Complete | `0008_memory_proposals` | `47e905d` |
| 26 | Explicit proposal promotion | Complete | `0008_memory_proposals` | `0092ded` |
| 27 | Developer workflow and safety automation | Complete | `0008_memory_proposals` | This commit |
| 28 | Memory duplicate and similarity detection | Complete | `0008_memory_proposals` | `12d39bf` |
| 29 | Advisory Memory contradiction detection | Complete | `0008_memory_proposals` | `4a96e56` |
| 30 | Windows Full verification process reliability | Complete | `0008_memory_proposals` | `86245e2` |
| 31 | Explicit Memory superseding workflow | Complete | `0008_memory_proposals` | `af9e56f` |
| 32 | Explicit Memory expiration workflow | Complete | `0009_memory_expiration` | `7b34eb6` |
| 33 | Explicit Memory quality refinement | Complete | `0009_memory_expiration` | `fce8e7c` |
| 34 | Evidence-backed Memory answers | Complete | `0009_memory_expiration` | `d1f3006` |
| 35 | Retrieval quality evaluation harness | Complete | `0009_memory_expiration` | `e1c3f4f` |
| 36 | Explicit batch Memory embedding generation | Complete | `0009_memory_expiration` | `d976b9a` |
| 37 | Controlled batch Memory re-embedding | Complete | `0009_memory_expiration` | `8af0e6a` |
| 38 | Read-only Memory maintenance audit | Complete | `0009_memory_expiration` | `5853269` |
| 39 | Versioned Project export bundle | Complete | `0009_memory_expiration` | `9045fbf` |
| 40 | Controlled Project import and restore | Complete | `0009_memory_expiration` | `029d936` |
| 41 | Operational diagnostics and configuration validation | Complete | `0009_memory_expiration` | `1f3023e` |
| 42 | Local web UI foundation | Complete | `0009_memory_expiration` | `a78b4cb` |
| 43 | Project retrieval API and Projects UI | Complete | `0009_memory_expiration` | `f8495de` |
| 44 | Sources browser and Source creation UI | Complete | `0009_memory_expiration` | `892791f` |
| 45 | Document ingestion and document browser UI | Complete | `0009_memory_expiration` | `c0716b1` |
| 46 | Proposal generation, review, and promotion UI | Complete | `0009_memory_expiration` | `00e8420` |
| 47 | Memories browser and quality actions UI | Complete | `0009_memory_expiration` | `0fb1705` |
| 48 | Lexical, semantic, and hybrid search UI | Complete | `0009_memory_expiration` | `3c469f0` |
| 49 | Evidence-backed answers UI | Complete | `0009_memory_expiration` | `3fb5b7b` |
| 50 | Read-only operations and Settings dashboard | Complete | `0009_memory_expiration` | `c9112a5` |
| 51 | Controlled Project export and import UI | Complete | `0009_memory_expiration` | `cf7e70a` |
| 52 | Local V1 release hardening and acceptance | Complete | `0009_memory_expiration` | `a1bf40c` |
| 53 | Post-release documentation synchronization | Complete | `0009_memory_expiration` | `bcd1e21` |
| 54 | V1.1 roadmap and technical planning | Complete | `0009_memory_expiration` | `21b5dc1` |
| 55 | React Router 8 security remediation and baseline alignment | Complete | `0009_memory_expiration` | `cefdc4e` |
| 56 | Non-authoritative GitHub Actions CI | Complete | `0009_memory_expiration` | `2c4ed44` |
| 57 | Additive explained Memory search backend | Complete | `0009_memory_expiration` | `f6b9260` |
| 58 | Explained search frontend and accessibility | Complete | `0009_memory_expiration` | `ccef163` |
| 59 | Local V1.1 end-to-end acceptance | Complete | `0009_memory_expiration` | `42fdfc8` |
| 60 | Local V1.1 documentation and release hardening | Complete | `0009_memory_expiration` | `88dffa9` |
| 61 | V1.2 Agent roadmap and threat model | Complete | `0009_memory_expiration` | `850cfd0` |
| 62 | Agent Runtime persistence foundation | Complete | `0010_agent_runtime_persistence` | `3da0cdd` |
| 63 | Agent Run state machine and API | Complete | `0010_agent_runtime_persistence` | `01832a9` |
| 64 | Tool Registry and policy enforcement | Complete | `0010_agent_runtime_persistence` | `35950c6` |
| 65 | Structured planning provider | Complete | `0010_agent_runtime_persistence` | `1b32d91` |
| 66 | Bounded read-only executor | Complete | `0010_agent_runtime_persistence` | `d4a3533` |
| 67 | Idempotency, cancellation, recovery, and failure injection | Complete | `0010_agent_runtime_persistence` | `7b6c6bb` |
| 68 | Approval and proposed-action foundation | Complete | `0010_agent_runtime_persistence` | `1bc90b4` |
| 69 | Agent Runs and Approval UI | Complete | `0010_agent_runtime_persistence` | `e6324e5` |
| 70 | Read-only Research Agent | Complete | `0010_agent_runtime_persistence` | `12a70f5` |
| 71 | Advisory Memory Curator Agent | Complete | `0010_agent_runtime_persistence` | `1dd8e83` |
| 72 | Agent security and evaluation harness | Complete | `0010_agent_runtime_persistence` | `45e940e` |
| 73 | Local V1.2 end-to-end acceptance | Complete | `0010_agent_runtime_persistence` | `26c74cc` |
| 74 | Local V1.2 release hardening | Complete | `0010_agent_runtime_persistence` | `53d78f3` |
| Patch | Local V1.2.1 Agent live-provider hotfix | Complete | `0010_agent_runtime_persistence` | `a8530ad` |
| 75 | Local V1.3 Architecture, Roadmap, and Threat Model | Complete | `0010_agent_runtime_persistence` | This commit |
| 76 | Automation persistence foundation | Complete | `0011_automation_persistence` | This commit |
| 77 | Automation API and lifecycle | Complete | `0011_automation_persistence` | This commit |
| 78 | Scheduler materialization and claiming | Complete | `0011_automation_persistence` | This commit |
| 79 | Restart, recovery, idempotency, and missed-run policy | Complete | `0011_automation_persistence` | This commit |
| 80 | Automatic read-only scheduled Agent execution | Complete | `0011_automation_persistence` | This commit |
| 81 | Automations UI and local notification inbox | Complete | `0011_automation_persistence` | This commit |
| 82 | Daily Brief Agent v1 | Complete | `0011_automation_persistence` | This commit |
| 83 | Project Watch Agent v1 | Complete | `0011_automation_persistence` | This commit |

## Standard lifecycle

1. Confirm a clean repository.
2. Start a new Codex conversation with the handoff and checkpoint request.
3. Implement one checkpoint.
4. Run complete verification.
5. Produce the checkpoint report.
6. Obtain human review.
7. Commit only after approval.
8. Push.
9. Confirm the repository is clean and matches the remote.
10. Begin the next checkpoint.
