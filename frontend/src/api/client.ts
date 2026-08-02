const DEFAULT_API_BASE = "/api";
const REQUEST_TIMEOUT_MS = 5_000;

export type HealthResponse = { status: "ok" };
export type ReadinessResponse = { status: "ready" };
export type ProjectRead = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};
export type ProjectCreate = { name: string; description: string | null };
export type SourceRead = {
  id: string;
  source_type: string;
  name: string;
  reference: string | null;
  checksum: string | null;
  created_at: string;
  updated_at: string;
};
export type SourceCreate = {
  source_type: string;
  name: string;
  reference: string | null;
  checksum: string | null;
};
export type LinkedMemoryRead = {
  link_id: string;
  source_id: string;
  memory_id: string;
  source_location: string | null;
  linked_at: string;
  project_id: string | null;
  title: string | null;
};
export type SourceDocumentRead = {
  id: string; source_id: string; media_type: string; original_filename: string | null;
  byte_size: number | null; ingestion_status: string; error_code: string | null;
  extracted_at: string | null; created_at: string; updated_at: string; chunk_count: number;
};
export type SourceChunkRead = {
  id: string; document_id: string; chunk_index: number; content: string;
  char_start: number; char_end: number; content_hash: string; locator: string | null;
  created_at: string;
};
export type TextIngestion = { text: string; original_filename: string | null; chunk_size: number; chunk_overlap: number };
export type ReviewStatus = "pending" | "approved" | "rejected";
export type MemoryProposal = {
  id: string; run_id: string; source_id: string; document_id: string; source_chunk_id: string | null;
  project_id: string | null; proposal_index: number; title: string | null; summary: string | null;
  content: string; memory_type: "working" | "episodic" | "semantic" | "decision" | "procedural" | "preference" | "temporary";
  importance: number; confidence: number; source_locator: string | null; review_status: ReviewStatus;
  review_note: string | null; reviewed_at: string | null; memory_id: string | null; created_at: string;
  updated_at: string; source_type: string; source_name: string; original_filename: string | null;
  run_provider: string; run_model: string; run_prompt_version: string;
};
export type MemoryProposalDetail = MemoryProposal & {
  source_chunk_hash: string; evidence_text: string; evidence_char_start: number; evidence_char_end: number;
  proposal_hash: string; run_status: "pending" | "completed" | "failed"; source_chunk_available: boolean;
};
export type ProposalGeneration = { id: string; proposal_count: number };
export type MemoryStatus = "active" | "superseded" | "invalid" | "archived" | "expired";
export type MemoryRead = {
  id: string; project_id: string | null; content: string; source: string | null;
  title: string | null; summary: string | null; memory_type: "working" | "episodic" | "semantic" | "decision" | "procedural" | "preference" | "temporary";
  importance: number; confidence: number; status: MemoryStatus; event_time: string | null;
  expires_at: string | null; supersedes_id: string | null; created_at: string; updated_at: string;
};
export type LinkedSource = {
  link_id: string; memory_id: string; source_id: string; source_location: string | null;
  linked_at: string; source_type: string; name: string; reference: string | null;
  checksum: string | null; source_created_at: string; source_updated_at: string;
};
export type SimilarityRead = { target_memory_id: string; candidates: Array<{ memory_id: string; classification: "exact_duplicate" | "similar"; lexical_similarity: number | null; semantic_similarity: number | null; reason: string }> };
export type ContradictionRead = { target_memory_id: string; candidates: Array<{ memory_id: string; classification: "potential_contradiction"; evidence_type: "explicit_negation" | "opposing_boolean_state"; reason: string; lexical_similarity: number | null; semantic_similarity: number | null; target_state: string; candidate_state: string }> };

export class SafeApiError extends Error {
  constructor() {
    super("The local API is unavailable or returned an unexpected response.");
    this.name = "SafeApiError";
  }
}

export class ProjectNotFoundError extends Error {
  constructor() {
    super("Project not found.");
    this.name = "ProjectNotFoundError";
  }
}

export class SourceNotFoundError extends Error {
  constructor() {
    super("Source not found.");
    this.name = "SourceNotFoundError";
  }
}

export class SourceDocumentNotFoundError extends Error {
  constructor() { super("Source document not found."); this.name = "SourceDocumentNotFoundError"; }
}
export class ProposalNotFoundError extends Error { constructor() { super("Proposal not found."); this.name = "ProposalNotFoundError"; } }
export class MemoryNotFoundError extends Error { constructor() { super("Memory not found."); this.name = "MemoryNotFoundError"; } }
export class ApiConflictError extends Error { constructor() { super("The proposal changed. Refresh and try again."); this.name = "ApiConflictError"; } }

function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE;
  return typeof configured === "string" && configured.trim()
    ? configured.replace(/\/+$/, "")
    : DEFAULT_API_BASE;
}

function hasExactStatus(value: unknown, expected: string): boolean {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return Object.keys(record).length === 1 && record.status === expected;
}

async function request<T>(
  path: string,
  validate: (value: unknown) => value is T,
  externalSignal?: AbortSignal,
  init?: { method: "POST" | "PUT"; body?: unknown },
  notFoundError?: "project" | "source" | "document" | "proposal" | "memory",
): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const abort = () => controller.abort();
  externalSignal?.addEventListener("abort", abort, { once: true });

  try {
    const response = await fetch(`${apiBase()}${path}`, {
      method: init?.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(init && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      },
      ...(init ? { body: init.body instanceof FormData ? init.body : JSON.stringify(init.body) } : {}),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (notFoundError && response.status === 404) {
      if (notFoundError === "project") throw new ProjectNotFoundError();
      if (notFoundError === "source") throw new SourceNotFoundError();
      if (notFoundError === "document") throw new SourceDocumentNotFoundError();
      if (notFoundError === "proposal") throw new ProposalNotFoundError();
      throw new MemoryNotFoundError();
    }
    if (response.status === 409) throw new ApiConflictError();
    if (!response.ok) {
      throw new SafeApiError();
    }
    const payload: unknown = await response.json();
    if (!validate(payload)) {
      throw new SafeApiError();
    }
    return payload;
  } catch (error) {
    if (error instanceof ProjectNotFoundError || error instanceof SourceNotFoundError || error instanceof SourceDocumentNotFoundError || error instanceof ProposalNotFoundError || error instanceof MemoryNotFoundError || error instanceof ApiConflictError) {
      throw error;
    }
    throw new SafeApiError();
  } finally {
    window.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abort);
  }
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isProjectId(value: string): boolean {
  return UUID_PATTERN.test(value);
}

export const isSourceId = isProjectId;

const nullableUuid = (value: unknown): value is string | null => value === null || (typeof value === "string" && isProjectId(value));

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && !Number.isNaN(Date.parse(value));
}

const nullableTimestamp = (value: unknown): value is string | null => value === null || isTimestamp(value);
function isMemory(value: unknown): value is MemoryRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  const keys = ["confidence", "content", "created_at", "event_time", "expires_at", "id", "importance", "memory_type", "project_id", "source", "status", "summary", "supersedes_id", "title", "updated_at"];
  return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(keys.sort()) && typeof r.id === "string" && isProjectId(r.id) && nullableUuid(r.project_id) &&
    typeof r.content === "string" && [r.source, r.title, r.summary].every(isNullableString) &&
    ["working", "episodic", "semantic", "decision", "procedural", "preference", "temporary"].includes(r.memory_type as string) &&
    typeof r.importance === "number" && Number.isFinite(r.importance) && r.importance >= 0 && r.importance <= 1 && typeof r.confidence === "number" && Number.isFinite(r.confidence) && r.confidence >= 0 && r.confidence <= 1 &&
    ["active", "superseded", "invalid", "archived", "expired"].includes(r.status as string) && nullableTimestamp(r.event_time) && nullableTimestamp(r.expires_at) && nullableUuid(r.supersedes_id) && isTimestamp(r.created_at) && isTimestamp(r.updated_at);
}

function isLinkedSource(value: unknown): value is LinkedSource {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>; const keys = ["checksum", "link_id", "linked_at", "memory_id", "name", "reference", "source_created_at", "source_id", "source_location", "source_type", "source_updated_at"];
  return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(keys.sort()) && [r.link_id, r.memory_id, r.source_id].every(v => typeof v === "string" && isProjectId(v)) && [r.source_location, r.reference, r.checksum].every(isNullableString) && typeof r.name === "string" && typeof r.source_type === "string" && [r.linked_at, r.source_created_at, r.source_updated_at].every(isTimestamp);
}

const score = (value: unknown) => value === null || (typeof value === "number" && Number.isFinite(value));
function isSimilarity(value: unknown): value is SimilarityRead { if (typeof value !== "object" || value === null || Array.isArray(value)) return false; const r = value as Record<string, unknown>; return typeof r.target_memory_id === "string" && isProjectId(r.target_memory_id) && Array.isArray(r.candidates) && r.candidates.every(v => { if (typeof v !== "object" || v === null || Array.isArray(v)) return false; const c = v as Record<string, unknown>; return typeof c.memory_id === "string" && isProjectId(c.memory_id) && ["exact_duplicate", "similar"].includes(c.classification as string) && score(c.lexical_similarity) && score(c.semantic_similarity) && typeof c.reason === "string"; }); }
function isContradiction(value: unknown): value is ContradictionRead { if (typeof value !== "object" || value === null || Array.isArray(value)) return false; const r = value as Record<string, unknown>; return typeof r.target_memory_id === "string" && isProjectId(r.target_memory_id) && Array.isArray(r.candidates) && r.candidates.every(v => { if (typeof v !== "object" || v === null || Array.isArray(v)) return false; const c = v as Record<string, unknown>; return typeof c.memory_id === "string" && isProjectId(c.memory_id) && c.classification === "potential_contradiction" && ["explicit_negation", "opposing_boolean_state"].includes(c.evidence_type as string) && score(c.lexical_similarity) && score(c.semantic_similarity) && [c.reason, c.target_state, c.candidate_state].every(x => typeof x === "string"); }); }

export function listMemories(query: URLSearchParams, signal?: AbortSignal) { return request(`/memories?${query}`, (v): v is MemoryRead[] => Array.isArray(v) && v.every(isMemory), signal); }
export function getMemory(id: string, signal?: AbortSignal) { return request(`/memories/${id}`, isMemory, signal, undefined, "memory"); }
export function listMemorySources(id: string, signal?: AbortSignal) { return request(`/memories/${id}/sources?limit=100&offset=0`, (v): v is LinkedSource[] => Array.isArray(v) && v.every(isLinkedSource), signal, undefined, "memory"); }
export function getSimilarities(id: string, signal?: AbortSignal) { return request(`/memories/${id}/similarities?limit=10`, isSimilarity, signal, undefined, "memory"); }
export function getContradictions(id: string, signal?: AbortSignal) { return request(`/memories/${id}/contradictions?limit=10`, isContradiction, signal, undefined, "memory"); }
export function refineMemory(id: string, body: { confidence: number; importance: number }, signal?: AbortSignal) { return request(`/memories/${id}/quality`, (v): v is { refinement_status: "updated" | "unchanged"; memory: MemoryRead } => typeof v === "object" && v !== null && ["updated", "unchanged"].includes((v as Record<string, unknown>).refinement_status as string) && isMemory((v as Record<string, unknown>).memory), signal, { method: "POST", body }, "memory"); }
export function supersedeMemory(id: string, replacement_memory_id: string, signal?: AbortSignal) { return request(`/memories/${id}/supersede`, (v): v is { supersession_status: "updated" | "unchanged"; superseded_memory: MemoryRead; replacement_memory: MemoryRead } => { if (typeof v !== "object" || v === null || Array.isArray(v)) return false; const r = v as Record<string, unknown>; return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(["replacement_memory", "superseded_memory", "supersession_status"]) && ["updated", "unchanged"].includes(r.supersession_status as string) && isMemory(r.superseded_memory) && isMemory(r.replacement_memory); }, signal, { method: "POST", body: { replacement_memory_id } }, "memory"); }
export function expireMemory(id: string, signal?: AbortSignal) { return request(`/memories/${id}/expire`, (v): v is { expiration_status: "updated" | "unchanged"; memory: MemoryRead } => { if (typeof v !== "object" || v === null || Array.isArray(v)) return false; const r = v as Record<string, unknown>; return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(["expiration_status", "memory"]) && ["updated", "unchanged"].includes(r.expiration_status as string) && isMemory(r.memory); }, signal, { method: "POST" }, "memory"); }

function isProject(value: unknown): value is ProjectRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  return (
    JSON.stringify(keys) === JSON.stringify(["created_at", "description", "id", "name", "updated_at"]) &&
    typeof record.id === "string" && isProjectId(record.id) &&
    typeof record.name === "string" && record.name.length >= 1 && record.name.length <= 200 &&
    (record.description === null || typeof record.description === "string") &&
    isTimestamp(record.created_at) && isTimestamp(record.updated_at)
  );
}

function isProjectList(value: unknown): value is ProjectRead[] {
  return Array.isArray(value) && value.every(isProject);
}

export function listProjects(limit: number, offset: number, signal?: AbortSignal): Promise<ProjectRead[]> {
  return request(`/projects?limit=${limit}&offset=${offset}`, isProjectList, signal);
}

export function createProject(project: ProjectCreate, signal?: AbortSignal): Promise<ProjectRead> {
  return request("/projects", isProject, signal, { method: "POST", body: project });
}

export function getProject(projectId: string, signal?: AbortSignal): Promise<ProjectRead> {
  return request(`/projects/${projectId}`, isProject, signal, undefined, "project");
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isSource(value: unknown): value is SourceRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return JSON.stringify(Object.keys(record).sort()) === JSON.stringify([
    "checksum", "created_at", "id", "name", "reference", "source_type", "updated_at",
  ]) && typeof record.id === "string" && isSourceId(record.id) &&
    typeof record.source_type === "string" && record.source_type.length >= 1 && record.source_type.length <= 50 &&
    typeof record.name === "string" && record.name.length >= 1 && record.name.length <= 255 &&
    isNullableString(record.reference) && isNullableString(record.checksum) &&
    (record.checksum === null || record.checksum.length <= 64) &&
    isTimestamp(record.created_at) && isTimestamp(record.updated_at);
}

function isSourceList(value: unknown): value is SourceRead[] {
  return Array.isArray(value) && value.every(isSource);
}

function isLinkedMemory(value: unknown): value is LinkedMemoryRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const requiredKeys = ["confidence", "content", "event_time", "expires_at", "importance", "legacy_source", "link_id", "linked_at", "memory_created_at", "memory_id", "memory_type", "memory_updated_at", "project_id", "source_id", "source_location", "status", "summary", "supersedes_id", "title"];
  if (JSON.stringify(Object.keys(record).sort()) !== JSON.stringify(requiredKeys.sort())) return false;
  const nullableUuid = (item: unknown) => item === null || (typeof item === "string" && isSourceId(item));
  const nullableTimestamp = (item: unknown) => item === null || isTimestamp(item);
  return [record.link_id, record.source_id, record.memory_id].every((item) => typeof item === "string" && isSourceId(item)) &&
    (record.project_id === null || (typeof record.project_id === "string" && isSourceId(record.project_id))) &&
    isNullableString(record.source_location) && isNullableString(record.title) &&
    isNullableString(record.summary) && isNullableString(record.legacy_source) &&
    typeof record.content === "string" && typeof record.memory_type === "string" &&
    typeof record.status === "string" && typeof record.importance === "number" &&
    Number.isFinite(record.importance) && typeof record.confidence === "number" &&
    Number.isFinite(record.confidence) && isTimestamp(record.linked_at) &&
    isTimestamp(record.memory_created_at) && isTimestamp(record.memory_updated_at) &&
    nullableTimestamp(record.event_time) && nullableTimestamp(record.expires_at) &&
    nullableUuid(record.supersedes_id);
}

export function listSources(limit: number, offset: number, signal?: AbortSignal): Promise<SourceRead[]> {
  return request(`/sources?limit=${limit}&offset=${offset}`, isSourceList, signal);
}

export function createSource(source: SourceCreate, signal?: AbortSignal): Promise<SourceRead> {
  return request("/sources", isSource, signal, { method: "POST", body: source });
}

export function getSource(sourceId: string, signal?: AbortSignal): Promise<SourceRead> {
  return request(`/sources/${sourceId}`, isSource, signal, undefined, "source");
}

export function listSourceMemories(sourceId: string, signal?: AbortSignal): Promise<LinkedMemoryRead[]> {
  return request(`/sources/${sourceId}/memories?limit=100&offset=0`, (value): value is LinkedMemoryRead[] => Array.isArray(value) && value.every(isLinkedMemory), signal);
}

function isDocument(value: unknown): value is SourceDocumentRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const keys = ["byte_size", "chunk_count", "created_at", "error_code", "extracted_at", "id", "ingestion_status", "media_type", "original_filename", "source_id", "updated_at"];
  return JSON.stringify(Object.keys(record).sort()) === JSON.stringify(keys.sort()) &&
    typeof record.id === "string" && isSourceId(record.id) && typeof record.source_id === "string" && isSourceId(record.source_id) &&
    typeof record.media_type === "string" && isNullableString(record.original_filename) &&
    (record.byte_size === null || (Number.isInteger(record.byte_size) && (record.byte_size as number) >= 0)) &&
    typeof record.ingestion_status === "string" && isNullableString(record.error_code) &&
    (record.extracted_at === null || isTimestamp(record.extracted_at)) && isTimestamp(record.created_at) && isTimestamp(record.updated_at) &&
    Number.isInteger(record.chunk_count) && (record.chunk_count as number) >= 0;
}

function isIngestionResult(value: unknown): value is SourceDocumentRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const { generation_status: generationStatus, ...document } = value as Record<string, unknown>;
  return ["created", "updated", "unchanged"].includes(generationStatus as string) && isDocument(document);
}

function isChunk(value: unknown): value is SourceChunkRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const keys = ["char_end", "char_start", "chunk_index", "content", "content_hash", "created_at", "document_id", "id", "locator"];
  return JSON.stringify(Object.keys(record).sort()) === JSON.stringify(keys.sort()) &&
    typeof record.id === "string" && isSourceId(record.id) && typeof record.document_id === "string" && isSourceId(record.document_id) &&
    Number.isInteger(record.chunk_index) && (record.chunk_index as number) >= 0 && typeof record.content === "string" && record.content.trim().length > 0 &&
    Number.isInteger(record.char_start) && Number.isInteger(record.char_end) && (record.char_start as number) >= 0 && (record.char_end as number) > (record.char_start as number) &&
    typeof record.content_hash === "string" && /^[0-9a-f]{64}$/.test(record.content_hash) && isNullableString(record.locator) && isTimestamp(record.created_at);
}

export function listSourceDocuments(sourceId: string, limit: number, offset: number, signal?: AbortSignal): Promise<SourceDocumentRead[]> {
  return request(`/sources/${sourceId}/documents?limit=${limit}&offset=${offset}`, (value): value is SourceDocumentRead[] => Array.isArray(value) && value.every(isDocument), signal, undefined, "source");
}
export function getSourceDocument(documentId: string, signal?: AbortSignal): Promise<SourceDocumentRead> {
  return request(`/source-documents/${documentId}`, isDocument, signal, undefined, "document");
}
export function listSourceChunks(documentId: string, limit: number, offset: number, signal?: AbortSignal): Promise<SourceChunkRead[]> {
  return request(`/source-documents/${documentId}/chunks?limit=${limit}&offset=${offset}`, (value): value is SourceChunkRead[] => Array.isArray(value) && value.every(isChunk), signal, undefined, "document");
}
export function ingestSourceText(sourceId: string, body: TextIngestion, signal?: AbortSignal): Promise<SourceDocumentRead> {
  return request(`/sources/${sourceId}/document/text`, isIngestionResult, signal, { method: "PUT", body }, "source");
}
export function ingestSourceFile(sourceId: string, body: FormData, signal?: AbortSignal): Promise<SourceDocumentRead> {
  return request(`/sources/${sourceId}/document/file`, isIngestionResult, signal, { method: "PUT", body }, "source");
}

const proposalKeys = ["confidence", "content", "created_at", "document_id", "id", "importance", "memory_id", "memory_type", "original_filename", "project_id", "proposal_index", "review_note", "review_status", "reviewed_at", "run_id", "run_model", "run_prompt_version", "run_provider", "source_chunk_id", "source_id", "source_locator", "source_name", "source_type", "summary", "title", "updated_at"];
function isProposal(value: unknown): value is MemoryProposal {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>; const nullableUuid = (v: unknown) => v === null || (typeof v === "string" && isSourceId(v));
  return JSON.stringify(Object.keys(r).sort()) === JSON.stringify([...proposalKeys].sort()) &&
    [r.id, r.run_id, r.source_id, r.document_id].every((v) => typeof v === "string" && isSourceId(v)) && nullableUuid(r.source_chunk_id) && nullableUuid(r.project_id) && nullableUuid(r.memory_id) &&
    Number.isInteger(r.proposal_index) && typeof r.content === "string" && ["working", "episodic", "semantic", "decision", "procedural", "preference", "temporary"].includes(r.memory_type as string) &&
    typeof r.importance === "number" && r.importance >= 0 && r.importance <= 1 && typeof r.confidence === "number" && r.confidence >= 0 && r.confidence <= 1 &&
    ["pending", "approved", "rejected"].includes(r.review_status as string) && [r.title, r.summary, r.source_locator, r.review_note, r.original_filename].every(isNullableString) &&
    (r.reviewed_at === null || isTimestamp(r.reviewed_at)) && isTimestamp(r.created_at) && isTimestamp(r.updated_at) &&
    [r.source_type, r.source_name, r.run_provider, r.run_model, r.run_prompt_version].every((v) => typeof v === "string");
}
function isProposalDetail(value: unknown): value is MemoryProposalDetail {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>; const detailKeys = ["evidence_char_end", "evidence_char_start", "evidence_text", "proposal_hash", "run_status", "source_chunk_available", "source_chunk_hash"];
  const base = Object.fromEntries(Object.entries(r).filter(([key]) => !detailKeys.includes(key)));
  return isProposal(base) && JSON.stringify(Object.keys(r).sort()) === JSON.stringify([...proposalKeys, ...detailKeys].sort()) &&
    typeof r.evidence_text === "string" && Number.isInteger(r.evidence_char_start) && Number.isInteger(r.evidence_char_end) &&
    typeof r.source_chunk_hash === "string" && /^[0-9a-f]{64}$/.test(r.source_chunk_hash) && typeof r.proposal_hash === "string" && /^[0-9a-f]{64}$/.test(r.proposal_hash) &&
    ["pending", "completed", "failed"].includes(r.run_status as string) && typeof r.source_chunk_available === "boolean";
}
export function listMemoryProposals(status: ReviewStatus | "all", projectId: string, limit: number, offset: number, signal?: AbortSignal) {
  const query = new URLSearchParams({ review_status: status, limit: String(limit), offset: String(offset) }); if (projectId) query.set("project_id", projectId);
  return request(`/memory-proposals?${query}`, (v): v is MemoryProposal[] => Array.isArray(v) && v.every(isProposal), signal);
}
export function getMemoryProposal(id: string, signal?: AbortSignal) { return request(`/memory-proposals/${id}`, isProposalDetail, signal, undefined, "proposal"); }
export function reviewMemoryProposal(id: string, decision: "approve" | "reject", note: string | null, signal?: AbortSignal) {
  return request(`/memory-proposals/${id}/${decision}`, (v): v is MemoryProposalDetail & { transition_status: "updated" | "unchanged" } => typeof v === "object" && v !== null && ["updated", "unchanged"].includes((v as Record<string, unknown>).transition_status as string) && isProposalDetail(Object.fromEntries(Object.entries(v).filter(([k]) => k !== "transition_status"))), signal, { method: "POST", body: { review_note: note } }, "proposal");
}
export function promoteMemoryProposal(id: string, signal?: AbortSignal) {
  return request(`/memory-proposals/${id}/promote`, (v): v is { proposal_id: string; promotion_status: "created" | "unchanged"; memory: unknown } => typeof v === "object" && v !== null && isSourceId((v as Record<string, unknown>).proposal_id as string) && ["created", "unchanged"].includes((v as Record<string, unknown>).promotion_status as string) && typeof (v as Record<string, unknown>).memory === "object", signal, { method: "POST" }, "proposal");
}
export function generateMemoryProposals(sourceId: string, projectId: string | null, signal?: AbortSignal) {
  const keys = ["completed_at", "created_at", "document_id", "error_code", "generation_status", "id", "input_hash", "model", "project_id", "prompt_version", "proposal_count", "provider", "run_status", "started_at", "updated_at"];
  return request(`/sources/${sourceId}/memory-proposals`, (v): v is ProposalGeneration => { if (typeof v !== "object" || v === null || Array.isArray(v)) return false; const r = v as Record<string, unknown>; return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(keys.sort()) && isSourceId(r.id as string) && isSourceId(r.document_id as string) && (r.project_id === null || isSourceId(r.project_id as string)) && [r.started_at, r.completed_at, r.created_at, r.updated_at].every(isTimestamp) && [r.provider, r.model, r.prompt_version].every(x => typeof x === "string") && typeof r.input_hash === "string" && /^[0-9a-f]{64}$/.test(r.input_hash) && r.run_status === "completed" && isNullableString(r.error_code) && Number.isInteger(r.proposal_count) && ["created", "retried", "unchanged"].includes(r.generation_status as string); }, signal, { method: "POST", body: { project_id: projectId, chunk_start: 0, chunk_limit: 10, max_proposals_per_chunk: 3 } });
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request(
    "/health",
    (value): value is HealthResponse => hasExactStatus(value, "ok"),
    signal,
  );
}

export function getReadiness(signal?: AbortSignal): Promise<ReadinessResponse> {
  return request(
    "/ready",
    (value): value is ReadinessResponse => hasExactStatus(value, "ready"),
    signal,
  );
}
