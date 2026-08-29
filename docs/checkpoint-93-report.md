# Checkpoint 93 report - explicit audited ExternalItem import

Status: **Approved and complete after human review.**

## Architecture and contract

Checkpoint 93 adds the approved `0013_external_item_imports` migration and one
closed provenance table. Each row uniquely and restrictively links one exact
`external_items.id` to one exact `source_documents.id`; the resulting Source is
derived through the existing one-to-one document relationship. Provider,
account, resource/item identity, application/provider revision, content hash,
and captured nullable Project scope remain authoritative on the linked
ExternalItem and are not duplicated or serialized into arbitrary local fields.

Preview is a read-only account/item/captured-scope action over one current latest
revision. It returns a closed External/Untrusted projection, deterministic
normalized plain text, safe historical GitHub URL, and a SHA-256 confirmation
fingerprint. Confirmation accepts only exact revision, provider version, content
hash, and fingerprint alongside path/scope identifiers. It locks and rereads the
ExternalItem, recomputes the projection and fingerprint, and conflicts on drift.

The fingerprint uses sorted compact UTF-8 JSON containing the fixed
`second-brain:external-item-import:v1` domain plus account ID, ExternalItem row
and immutable resource/item identities, application revision, trust label,
captured scope, resource type, title, normalized text, provider source version,
content hash, and nullable canonical URL. It contains no secret or credential.

## Ingestion, safety, and idempotency

Confirmation creates one `connector_import` Source, one extracted `text/plain`
SourceDocument, deterministic 2,000-character chunks with 200-character overlap,
and one provenance row in the route-owned transaction. Source name is the
bounded snapshot title/fixed fallback, reference is only the reconstructed safe
historical URL, checksum is the exact snapshot content hash, and original
filename is null. No client content or settings are accepted.

The ExternalItem row lock serializes identical confirmations and the unique
ExternalItem provenance key resolves replay to the existing Source/Document.
Newer application revisions use distinct ExternalItem rows and never overwrite
older imports. Any exception before route commit rolls back Source, document,
chunks, and provenance together. Current historical snapshots remain explicitly
importable after account disable/revoke because import performs no provider or
credential operation and uses captured item scope rather than current account
configuration.

Import renders and stores hostile text as inert plain text and creates no
Memory, MemoryProposal, Approval, AgentRun, or Automation state. There is no
bulk/background/automatic import, polling, scheduling, Agent/Automation
authority, external write, GitHub call, credential lookup, proposal generation,
promotion, or Checkpoint 94 behavior.

## Stable boundaries and verification

The Checkpoint 91 GET-only request inventory and `agent-tools-v1` registry are
unchanged. Project export remains `second-brain-project-export` version `1`;
connector provenance is excluded, while resulting local records follow only the
pre-existing export-v1 selection rules.

Focused verification passed **9 backend tests** and **2 frontend tests**, zero
skips. The final authoritative host-context `scripts/verify.ps1 -Mode Full`
passed **1,174 backend tests** and **135 frontend tests in 14 files**, zero
skips, plus pip check, Ruff lint/format, strict mypy over 176 production files,
database identities, Alembic current/head/check, ESLint, TypeScript, production
build, and `git diff --check`. Alembic current and sole head are
`0013_external_item_imports`; autogenerate reports no pending operations.
