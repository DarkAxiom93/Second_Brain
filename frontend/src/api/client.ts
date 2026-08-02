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
  init?: { method: "POST" | "PUT"; body: ProjectCreate | SourceCreate | TextIngestion | FormData },
  notFoundError?: "project" | "source" | "document",
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
      throw new SourceDocumentNotFoundError();
    }
    if (!response.ok) {
      throw new SafeApiError();
    }
    const payload: unknown = await response.json();
    if (!validate(payload)) {
      throw new SafeApiError();
    }
    return payload;
  } catch (error) {
    if (error instanceof ProjectNotFoundError || error instanceof SourceNotFoundError || error instanceof SourceDocumentNotFoundError) {
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

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && !Number.isNaN(Date.parse(value));
}

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
