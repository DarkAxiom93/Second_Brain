[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][Guid]$SourceId,
    [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$ExpectedName,
    [ValidateRange(-1, 2147483647)][int]$ExpectedDocuments = -1,
    [ValidateRange(-1, 2147483647)][int]$ExpectedChunks = -1,
    [ValidateRange(-1, 2147483647)][int]$ExpectedRuns = -1,
    [ValidateRange(-1, 2147483647)][int]$ExpectedProposals = -1,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = "postgresql+psycopg://second_brain:change-me@127.0.0.1:5433/second_brain" }
$env:SMOKE_SOURCE_ID = $SourceId.ToString()
$env:SMOKE_EXPECTED_NAME = $ExpectedName
$env:SMOKE_EXPECTED_DOCUMENTS = [string]$ExpectedDocuments
$env:SMOKE_EXPECTED_CHUNKS = [string]$ExpectedChunks
$env:SMOKE_EXPECTED_RUNS = [string]$ExpectedRuns
$env:SMOKE_EXPECTED_PROPOSALS = [string]$ExpectedProposals
$env:SMOKE_EXECUTE = if ($Execute) { "1" } else { "0" }

$code = @'
import os
import uuid
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.models import Memory, MemoryEmbedding, MemoryExtractionRun, MemoryProposal, Project, Source, SourceChunk, SourceDocument
from app.models.memory_source import MemorySource

url = make_url(os.environ["DATABASE_URL"])
if url.host != "127.0.0.1" or url.database != "second_brain":
    raise SystemExit("Cleanup refused: DATABASE_URL identity is unsafe")
engine = create_engine(os.environ["DATABASE_URL"])
source_id = uuid.UUID(os.environ["SMOKE_SOURCE_ID"])
expected_name = os.environ["SMOKE_EXPECTED_NAME"]
expected = {k: int(os.environ[v]) for k, v in (("documents", "SMOKE_EXPECTED_DOCUMENTS"), ("chunks", "SMOKE_EXPECTED_CHUNKS"), ("runs", "SMOKE_EXPECTED_RUNS"), ("proposals", "SMOKE_EXPECTED_PROPOSALS"))}
execute = os.environ["SMOKE_EXECUTE"] == "1"

with Session(engine) as session:
    if session.scalar(text("SELECT current_database()")) != "second_brain":
        raise SystemExit("Cleanup refused: live database identity is unsafe")
    source = session.get(Source, source_id)
    if source is None: raise SystemExit("Cleanup refused: exact Source UUID was not found")
    if source.name != expected_name: raise SystemExit("Cleanup refused: exact Source name does not match")
    document_ids = list(session.scalars(select(SourceDocument.id).where(SourceDocument.source_id == source_id)))
    chunk_ids = list(session.scalars(select(SourceChunk.id).where(SourceChunk.document_id.in_(document_ids)))) if document_ids else []
    run_ids = list(session.scalars(select(MemoryExtractionRun.id).where(MemoryExtractionRun.document_id.in_(document_ids)))) if document_ids else []
    proposal_ids = list(session.scalars(select(MemoryProposal.id).where(MemoryProposal.run_id.in_(run_ids)))) if run_ids else []
    counts = {"documents": len(document_ids), "chunks": len(chunk_ids), "runs": len(run_ids), "proposals": len(proposal_ids)}
    for key, wanted in expected.items():
        if wanted >= 0 and counts[key] != wanted: raise SystemExit(f"Cleanup refused: expected {key} count mismatch")
    linked_memories = session.scalar(select(func.count()).select_from(MemorySource).where(MemorySource.source_id == source_id))
    if linked_memories: raise SystemExit("Cleanup refused: Source is linked to Memory records")
    protected_before = {"memories": session.scalar(select(func.count()).select_from(Memory)), "embeddings": session.scalar(select(func.count()).select_from(MemoryEmbedding)), "projects": session.scalar(select(func.count()).select_from(Project)), "other_sources": session.scalar(select(func.count()).select_from(Source).where(Source.id != source_id))}
    print(f"Source id={source_id} name={source.name!r} documents={counts['documents']} chunks={counts['chunks']} runs={counts['runs']} proposals={counts['proposals']}")
    if not execute:
        session.rollback(); print("Dry run complete; no rows were deleted."); raise SystemExit(0)
    session.delete(source); session.flush()
    if session.get(Source, source_id) is not None: raise RuntimeError("Source deletion verification failed")
    for model, ids in ((SourceDocument, document_ids), (SourceChunk, chunk_ids), (MemoryExtractionRun, run_ids), (MemoryProposal, proposal_ids)):
        if ids and session.scalar(select(func.count()).select_from(model).where(model.id.in_(ids))) != 0: raise RuntimeError("Owned-row deletion verification failed")
    protected_after = {"memories": session.scalar(select(func.count()).select_from(Memory)), "embeddings": session.scalar(select(func.count()).select_from(MemoryEmbedding)), "projects": session.scalar(select(func.count()).select_from(Project)), "other_sources": session.scalar(select(func.count()).select_from(Source).where(Source.id != source_id))}
    if protected_after != protected_before: raise RuntimeError("Protected or unrelated row counts changed")
    session.commit(); print("Exact smoke Source and its approved cascades were deleted.")
engine.dispose()
'@
Push-Location $repoRoot
try {
    $code | & $python -
    if ($LASTEXITCODE -ne 0) { throw "Smoke Source cleanup checks failed; transaction was rolled back." }
} finally { Pop-Location }
