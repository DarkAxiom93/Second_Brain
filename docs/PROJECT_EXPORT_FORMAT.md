# Project export bundle

`second-brain-project-export` version 1 is a private, application-level backup
of one Project. It is not `pg_dump`. The format version is unchanged across the
additive Agent Runtime migration: controlled import accepts source bundles made
at exactly `0009_memory_expiration`, `0010_agent_runtime_persistence`, or
`0011_automation_persistence`, while
the current export and import target database must be exactly
`0011_automation_persistence`. Every other source or target revision fails
closed.

The `.sbexport` file is a ZIP-compatible container owned by this application.
It contains `manifest.json`, `project.json`, and the always-present JSONL files
`memories`, `memory_embeddings`, `sources`, `memory_sources`,
`source_documents`, `source_chunks`, `memory_extraction_runs`, and
`memory_proposals`. Every persisted field is retained except the generated
Memory search vector. UUIDs are strings; null fields remain explicit; UTC
timestamps use ISO-8601 with six fractional digits and `Z`; JSON keys and rows
are deterministic; files use UTF-8 and LF.

Memories and extraction runs must directly name the requested Project.
Embeddings and MemorySource links follow only exported Memories. Sources have
no Project owner in the current schema, so the bundle includes only Sources
linked to exported Memories or owning documents used by included runs.
Documents follow included runs, chunks follow those documents, and proposals
must belong both to an included run and the requested Project. Shared Sources
never broaden Memory, document, run, or proposal selection.

All references are checked before publication. A non-null supersession,
promoted-Memory, or proposal-chunk reference outside the bundle makes export
fail; references are never silently dropped or rewritten. The manifest records
the Alembic revision, safe Project identity, entity counts, and byte length,
row count, and SHA-256 for every data file. `manifest.json` is the checksum
index and therefore does not recursively checksum itself.

All reads use one PostgreSQL `REPEATABLE READ`, `READ ONLY` transaction. Large
JSONL content is streamed. A temporary sibling file is renamed to the requested
path only after serialization and integrity validation. Parent directories
must already exist, and an existing output is never overwritten.

```powershell
.\scripts\export-project.ps1 -ProjectId <uuid> -OutputPath C:\backup\project.sbexport
.\scripts\export-project.ps1 -ProjectId <uuid> -OutputPath C:\backup\test.sbexport -UseTestDatabase
```

The bundle is sensitive private data. It may contain Memory content, extracted
document and chunk text, evidence snapshots, filenames, Source metadata, and
embedding vectors. Version 1 is not encrypted and must not be published or sent
unprotected. It contains no database URLs, credentials, environment variables,
provider responses, prompts, reasoning, generated search vectors, logs, or
temporary paths.

Agent Runs, Agent Steps, Tool Invocations, Approval Requests, Agent Events, raw
provider or Tool payloads, private execution identities, and other Agent runtime
state are not version-1 data files and are never exported or imported. Importing
a version-1 bundle neither creates nor mutates that state.

## Controlled import

Validation-only is the default and performs no flush or commit:

```powershell
.\scripts\import-project.ps1 -BundlePath C:\backup\project.sbexport
.\scripts\import-project.ps1 -BundlePath C:\backup\test.sbexport -UseTestDatabase
```

Execution requires an explicit manifest Project ID match:

```powershell
.\scripts\import-project.ps1 -BundlePath C:\backup\project.sbexport -Execute -ExpectedProjectId <uuid>
.\scripts\import-project.ps1 -BundlePath C:\backup\test.sbexport -UseTestDatabase -Execute -ExpectedProjectId <uuid>
```

Import validates the complete archive, manifest, schemas, checksums, counts,
typed values, references, supersession graph, target identities, and unique
constraints before writing. Every imported identity must be absent. Existing
rows are never merged, overwritten, reused, remapped, repaired, or deleted.
Execution inserts the complete graph in dependency-safe deterministic order in
one caller-owned transaction and commits exactly once; any failure rolls back
the whole Project. Generated Memory search vectors are omitted from the bundle
and PostgreSQL derives them from restored persisted fields.

The reader does not extract archive contents. Limits are 32 entries, 128 MiB
for the archive and total compressed entry data, 64 MiB per compressed or
uncompressed entry, 256 MiB total uncompressed data, and 4 MiB per JSONL row.
Absolute, traversing, duplicate, case-colliding, encrypted, and non-regular
entries are rejected.

An export/import/export round trip preserves canonical application data-file
content and relationships; only package metadata such as export time and ZIP
byte layout may vary. Version 1 has no encryption, merge, remapping,
partial-restore, or automatic restore facility.

## Local operations API and UI

The Settings UI lists Projects in bounded pages and exports only after an
explicit action. `POST /operations/project-exports/{project_id}` returns one
streamed `.sbexport` attachment. The browser accepts only a reviewed UUID-based
filename, does not persist the bundle, and revokes its temporary object URL.

Import uses raw streamed request bodies rather than multipart forms or client
filesystem paths. `POST /operations/project-imports/validate` performs complete
archive, graph, revision, database-identity, and conflict validation without a
flush, commit, or persistent write. Its safe plan contains only format and
Project identity, revision, entity counts, bundle SHA-256, and concise warning
or conflict categories. A valid conflicting bundle is distinct from a malformed
bundle.

`POST /operations/project-imports/execute` requires the manifest Project UUID
and validated bundle SHA-256, then revalidates the same uploaded bytes and all
target conflicts before one atomic commit. It never merges, overwrites, remaps,
repairs, partially imports, or records import history. All three routes accept
only direct IPv4/IPv6 loopback clients, ignore forwarding headers, require a
distinct exact `X-Second-Brain-Operation` value, and return `Cache-Control:
no-store`. Request-owned temporary files are unique and exactly removed after
success or failure. Bundles remain private and unencrypted.
