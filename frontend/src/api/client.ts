const DEFAULT_API_BASE = "/api";
const REQUEST_TIMEOUT_MS = 5_000;

export type HealthResponse = { status: "ok" };
export type ReadinessResponse = { status: "ready" };
export type DiagnosticStatus = "passed" | "warning" | "failed";
export type OperationsDiagnostics = {
  diagnostics_status: "healthy" | "unhealthy";
  captured_at: string;
  warning_count: number;
  failure_count: number;
  checks: Array<{ check_id: string; category: string; status: DiagnosticStatus; message: string }>;
  aggregate_counts: Record<string, number>;
};
export type OperationsMaintenanceAudit = {
  captured_at: string;
  total_memories: number;
  project_assigned_memories: number;
  unassigned_memories: number;
  counts_by_status: Record<string, number>;
  findings: Array<{ finding_id: string; count: number }>;
};
export type ProjectImportPlan = {
  validation_status: "valid"; importable: boolean; format_name: string; format_version: number;
  project_id: string; project_name: string; source_alembic_revision: string;
  entity_counts: Record<string, number>; bundle_sha256: string; conflicts: string[];
  warnings: string[]; conflict_count: number; warning_count: number;
};
export type ProjectImportResult = Omit<ProjectImportPlan, "validation_status" | "importable" | "conflicts" | "warnings" | "conflict_count" | "warning_count"> & { import_status: "imported" };
export type ProjectExportDownload = { blob: Blob; filename: string };
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
export type SearchMode = "lexical" | "semantic" | "hybrid";
export type AnswerRequest = { query: string; project_id: string | null; search_mode: SearchMode; limit: number };
export type AnswerCitation = { label: string; rank: number; memory: MemoryRead; lexical_score: number | null; semantic_score: number | null };
export type AnswerRead = { answer_status: "answered" | "insufficient_evidence"; answer: string; search_mode: SearchMode; citations: AnswerCitation[] };
export type MemorySearchFilters = {
  project_id?: string; memory_type?: MemoryRead["memory_type"]; status?: MemoryStatus;
  importance_min?: number; importance_max?: number; confidence_min?: number; confidence_max?: number;
};
export type MemorySearchChannel = "lexical" | "semantic";
export type ExplainedMemorySearchRequest = {
  query: string; mode: SearchMode; filters: MemorySearchFilters;
  pagination: { limit: number; offset: 0 };
};
export type MemorySearchExplanation = {
  mode: SearchMode; matched_by: MemorySearchChannel[];
  lexical_rank: number | null; semantic_rank: number | null;
  lexical_signal: number | null; semantic_signal: number | null;
  lexical_rrf_contribution: number | null; semantic_rrf_contribution: number | null;
  fused_rrf_score: number | null;
};
export type ExplainedMemorySearchResult = { rank: number; memory: MemoryRead; explanation: MemorySearchExplanation };
export type LinkedSource = {
  link_id: string; memory_id: string; source_id: string; source_location: string | null;
  linked_at: string; source_type: string; name: string; reference: string | null;
  checksum: string | null; source_created_at: string; source_updated_at: string;
};
export type SimilarityRead = { target_memory_id: string; candidates: Array<{ memory_id: string; classification: "exact_duplicate" | "similar"; lexical_similarity: number | null; semantic_similarity: number | null; reason: string }> };
export type ContradictionRead = { target_memory_id: string; candidates: Array<{ memory_id: string; classification: "potential_contradiction"; evidence_type: "explicit_negation" | "opposing_boolean_state"; reason: string; lexical_similarity: number | null; semantic_similarity: number | null; target_state: string; candidate_state: string }> };
export type AgentRunState = "created" | "planning" | "ready" | "running" | "awaiting_approval" | "completed" | "failed" | "cancelled" | "expired";
export type AgentRun = { id: string; project_id: string | null; agent_kind: string; agent_version: string; goal_summary: string; registry_version: string; policy_version: string; state: AgentRunState; step_budget: number; tool_call_budget: number; retry_budget: number; planning_deadline: string; run_deadline: string; revision: number; safe_error_code: string | null; created_at: string; updated_at: string; started_at: string | null; finished_at: string | null };
export type AgentStep = { ordinal: number; purpose: string; tool_name: string; tool_version: number; normalized_input: Record<string, unknown>; expected_evidence: string[]; success_condition: string; stop_condition: string };
export type AgentPlan = { run: AgentRun; goal_summary: string; steps: AgentStep[] };
export type AgentExecutionStep = { ordinal: number; purpose: string; tool_name: string; tool_version: number; status: string; invocation_status: string | null; safe_result_summary: string | null; evidence_references: Array<Record<string, unknown>>; safe_error_code: string | null };
export type ResearchCitation = { number: number; entity_type: "project" | "memory" | "source" | "source_chunk"; entity_id: string; version: string };
export type ResearchClaim = { text: string; citation_numbers: number[] };
export type ResearchResult = { status: "answered" | "insufficient_evidence"; claims: ResearchClaim[]; citations: ResearchCitation[]; insufficiency: string | null };
export type CuratorResult = { findings: Array<{ text: string; evidence: Array<{ entity_type: "project" | "memory" | "source" | "source_chunk"; entity_id: string; version: string }> }>; proposed_actions: Array<{ approval_id: string; action_type: "memory.update"; target_id: string; target_version: string }> };
export type AgentExecution = { run: AgentRun; steps: AgentExecutionStep[]; research_result?: ResearchResult | null; curator_result?: CuratorResult | null };
export type ApprovalRequest = { id: string; run_id: string; step_ordinal: number; action_type: string; target_type: string; target_id: string; target_version: string; proposed_input: Record<string, unknown>; preview: string; evidence_references: Array<Record<string, unknown>>; risk_classification: string; status: "pending" | "approved" | "rejected" | "expired" | "superseded"; created_at: string; expires_at: string; reviewed_at: string | null };

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
export class AgentRunNotFoundError extends Error { constructor() { super("Agent Run not found."); this.name = "AgentRunNotFoundError"; } }
export class ApiConflictError extends Error { constructor() { super("The proposal changed. Refresh and try again."); this.name = "ApiConflictError"; } }
export class SearchProviderError extends Error { constructor(message: string) { super(message); this.name = "SearchProviderError"; } }
export class AnswerProviderError extends Error { constructor(message: string) { super(message); this.name = "AnswerProviderError"; } }
export class ImportConflictError extends Error { constructor() { super("The bundle now conflicts with the target or its confirmation is stale."); this.name = "ImportConflictError"; } }

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
  init?: { method: "POST" | "PUT"; body?: unknown; headers?: Record<string, string> },
  notFoundError?: "project" | "source" | "document" | "proposal" | "memory" | "agent-run",
  searchErrors = false,
  answerErrors = false,
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
        ...init?.headers,
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
      if (notFoundError === "agent-run") throw new AgentRunNotFoundError();
      throw new MemoryNotFoundError();
    }
    if (response.status === 409) throw new ApiConflictError();
    if (!response.ok) {
      if (searchErrors && [502, 503].includes(response.status)) {
        let detail = "";
        try { const value: unknown = await response.json(); if (typeof value === "object" && value !== null && (value as Record<string, unknown>).detail && typeof (value as Record<string, unknown>).detail === "string") detail = (value as Record<string, string>).detail; } catch { /* expose no response body */ }
        const safe: Record<string, string> = {
          "embedding provider unavailable": "Semantic search is not configured on this local workspace.",
          "embedding provider failed": "The embedding provider could not complete the search.",
          "invalid embedding response": "The embedding provider returned an unusable response.",
        };
        if (safe[detail]) throw new SearchProviderError(safe[detail]);
      }
      if (answerErrors && [502, 503].includes(response.status)) {
        let detail = "";
        try { const value: unknown = await response.json(); if (typeof value === "object" && value !== null && typeof (value as Record<string, unknown>).detail === "string") detail = (value as Record<string, string>).detail; } catch { /* expose no response body */ }
        const safe: Record<string, string> = {
          "embedding provider unavailable": "Semantic retrieval is not configured on this local workspace.",
          "embedding provider failed": "The embedding provider could not retrieve answer evidence.",
          "invalid embedding response": "The embedding provider returned an unusable response.",
          "answer provider unavailable": "Answer generation is not configured on this local workspace.",
          "answer provider failed": "The answer provider could not complete this request.",
          "database unavailable": "The local answer database is unavailable.",
        };
        if (safe[detail]) throw new AnswerProviderError(safe[detail]);
      }
      throw new SafeApiError();
    }
    const payload: unknown = await response.json();
    if (!validate(payload)) {
      throw new SafeApiError();
    }
    return payload;
  } catch (error) {
    if (error instanceof ProjectNotFoundError || error instanceof SourceNotFoundError || error instanceof SourceDocumentNotFoundError || error instanceof ProposalNotFoundError || error instanceof MemoryNotFoundError || error instanceof AgentRunNotFoundError || error instanceof ApiConflictError || error instanceof SearchProviderError || error instanceof AnswerProviderError) {
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
const objectRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
function isAgentRun(value: unknown): value is AgentRun {
  if (!objectRecord(value)) return false;
  const keys = ["id","project_id","agent_kind","agent_version","goal_summary","registry_version","policy_version","state","step_budget","tool_call_budget","retry_budget","planning_deadline","run_deadline","revision","safe_error_code","created_at","updated_at","started_at","finished_at"];
  return exactKeys(value, keys) && isProjectId(value.id as string) && nullableUuid(value.project_id) && [value.agent_kind,value.agent_version,value.goal_summary,value.registry_version,value.policy_version].every(v => typeof v === "string") && ["created","planning","ready","running","awaiting_approval","completed","failed","cancelled","expired"].includes(value.state as string) && [value.step_budget,value.tool_call_budget,value.retry_budget,value.revision].every(v => Number.isInteger(v) && (v as number) >= 0) && [value.planning_deadline,value.run_deadline,value.created_at,value.updated_at].every(isTimestamp) && nullableTimestamp(value.started_at) && nullableTimestamp(value.finished_at) && isNullableString(value.safe_error_code);
}
function isAgentStep(value: unknown): value is AgentStep { if (!objectRecord(value)) return false; return exactKeys(value,["ordinal","purpose","tool_name","tool_version","normalized_input","expected_evidence","success_condition","stop_condition"]) && Number.isInteger(value.ordinal) && typeof value.purpose === "string" && typeof value.tool_name === "string" && Number.isInteger(value.tool_version) && objectRecord(value.normalized_input) && Array.isArray(value.expected_evidence) && value.expected_evidence.every(v => typeof v === "string") && typeof value.success_condition === "string" && typeof value.stop_condition === "string"; }
function isAgentPlan(value: unknown): value is AgentPlan { return objectRecord(value) && exactKeys(value,["run","goal_summary","steps"]) && isAgentRun(value.run) && typeof value.goal_summary === "string" && Array.isArray(value.steps) && value.steps.every(isAgentStep); }
function isExecutionStep(value: unknown): value is AgentExecutionStep { if (!objectRecord(value)) return false; return exactKeys(value,["ordinal","purpose","tool_name","tool_version","status","invocation_status","safe_result_summary","evidence_references","safe_error_code"]) && Number.isInteger(value.ordinal) && typeof value.purpose === "string" && typeof value.tool_name === "string" && Number.isInteger(value.tool_version) && typeof value.status === "string" && isNullableString(value.invocation_status) && isNullableString(value.safe_result_summary) && Array.isArray(value.evidence_references) && value.evidence_references.every(objectRecord) && isNullableString(value.safe_error_code); }
function isResearchCitation(value: unknown): value is ResearchCitation { return objectRecord(value) && exactKeys(value,["number","entity_type","entity_id","version"]) && Number.isInteger(value.number) && ["project","memory","source","source_chunk"].includes(String(value.entity_type)) && isProjectId(value.entity_id as string) && typeof value.version === "string" && /^[0-9a-f]{64}$/.test(value.version); }
function isResearchClaim(value: unknown): value is ResearchClaim { return objectRecord(value) && exactKeys(value,["text","citation_numbers"]) && typeof value.text === "string" && Array.isArray(value.citation_numbers) && value.citation_numbers.every(Number.isInteger); }
function isResearchResult(value: unknown): value is ResearchResult { return objectRecord(value) && exactKeys(value,["status","claims","citations","insufficiency"]) && ["answered","insufficient_evidence"].includes(String(value.status)) && Array.isArray(value.claims) && value.claims.every(isResearchClaim) && Array.isArray(value.citations) && value.citations.every(isResearchCitation) && isNullableString(value.insufficiency); }
function isCuratorResult(value: unknown): value is CuratorResult { if (!objectRecord(value) || !exactKeys(value,["findings","proposed_actions"]) || !Array.isArray(value.findings) || !Array.isArray(value.proposed_actions)) return false; return value.findings.every(v => objectRecord(v) && exactKeys(v,["text","evidence"]) && typeof v.text === "string" && Array.isArray(v.evidence) && v.evidence.every(e => objectRecord(e) && exactKeys(e,["entity_type","entity_id","version"]) && ["project","memory","source","source_chunk"].includes(e.entity_type as string) && isProjectId(e.entity_id as string) && /^[0-9a-f]{64}$/.test(e.version as string))) && value.proposed_actions.every(v => objectRecord(v) && exactKeys(v,["approval_id","action_type","target_id","target_version"]) && isProjectId(v.approval_id as string) && v.action_type === "memory.update" && isProjectId(v.target_id as string) && /^[0-9a-f]{64}$/.test(v.target_version as string)); }
function isAgentExecution(value: unknown): value is AgentExecution { return objectRecord(value) && Object.keys(value).every(k => ["run","steps","research_result","curator_result"].includes(k)) && exactKeys({run:value.run,steps:value.steps},["run","steps"]) && isAgentRun(value.run) && Array.isArray(value.steps) && value.steps.every(isExecutionStep) && (value.research_result === undefined || value.research_result === null || isResearchResult(value.research_result)) && (value.curator_result === undefined || value.curator_result === null || isCuratorResult(value.curator_result)); }
function isApproval(value: unknown): value is ApprovalRequest { if (!objectRecord(value)) return false; return exactKeys(value,["id","run_id","step_ordinal","action_type","target_type","target_id","target_version","proposed_input","preview","evidence_references","risk_classification","status","created_at","expires_at","reviewed_at"]) && isProjectId(value.id as string) && isProjectId(value.run_id as string) && Number.isInteger(value.step_ordinal) && [value.action_type,value.target_type,value.target_version,value.preview,value.risk_classification].every(v => typeof v === "string") && isProjectId(value.target_id as string) && objectRecord(value.proposed_input) && Array.isArray(value.evidence_references) && value.evidence_references.every(objectRecord) && ["pending","approved","rejected","expired","superseded"].includes(value.status as string) && isTimestamp(value.created_at) && isTimestamp(value.expires_at) && nullableTimestamp(value.reviewed_at); }

export function listAgentRuns(signal?: AbortSignal) { return request("/agent-runs?limit=50&offset=0", (v): v is AgentRun[] => Array.isArray(v) && v.every(isAgentRun), signal); }
export function createAgentRun(body: { project_id: string | null; agent_kind: string; agent_version: string; goal_summary: string }, signal?: AbortSignal) { return request("/agent-runs", isAgentRun, signal, { method: "POST", body, headers: { "Idempotency-Key": crypto.randomUUID() } }); }
export function getAgentRun(id: string, signal?: AbortSignal) { return request(`/agent-runs/${id}`, isAgentRun, signal, undefined, "agent-run"); }
export function getAgentPlan(id: string, signal?: AbortSignal) { return request(`/agent-runs/${id}/plan`, isAgentPlan, signal); }
export function planAgentRun(id: string, revision: number, signal?: AbortSignal) { return request(`/agent-runs/${id}/plan`, isAgentPlan, signal, { method: "POST", body: { expected_revision: revision } }); }
export function getAgentExecution(id: string, signal?: AbortSignal) { return request(`/agent-runs/${id}/execution`, isAgentExecution, signal); }
export function executeAgentRun(id: string, revision: number, signal?: AbortSignal) { return request(`/agent-runs/${id}/execute`, isAgentExecution, signal, { method: "POST", body: { expected_revision: revision } }); }
export function cancelAgentRun(id: string, revision: number, signal?: AbortSignal) { return request(`/agent-runs/${id}/cancel`, isAgentRun, signal, { method: "POST", body: { expected_revision: revision } }); }
export function listApprovalRequests(id: string, signal?: AbortSignal) { return request(`/agent-runs/${id}/approval-requests?limit=50&offset=0`, (v): v is ApprovalRequest[] => Array.isArray(v) && v.every(isApproval), signal); }
export function reviewApproval(id: string, decision: "approve" | "reject", signal?: AbortSignal) { return request(`/approval-requests/${id}/review`, isApproval, signal, { method: "POST", body: { decision } }); }
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

const exactKeys = (record: Record<string, unknown>, keys: string[]) =>
  JSON.stringify(Object.keys(record).sort()) === JSON.stringify([...keys].sort());
const positiveIntegerOrNull = (value: unknown) => value === null || (Number.isInteger(value) && (value as number) > 0);
const boundedOrNull = (value: unknown) => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1);
const nonNegativeOrNull = (value: unknown) => value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);
function isExplanation(value: unknown): value is MemorySearchExplanation {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  if (!exactKeys(r, ["mode", "matched_by", "lexical_rank", "semantic_rank", "lexical_signal", "semantic_signal", "lexical_rrf_contribution", "semantic_rrf_contribution", "fused_rrf_score"])) return false;
  if (!["lexical", "semantic", "hybrid"].includes(r.mode as string) || !Array.isArray(r.matched_by)) return false;
  const channels = r.matched_by;
  if (!["lexical", "semantic"].every(channel => channels.filter(value => value === channel).length <= 1) || channels.some(value => value !== "lexical" && value !== "semantic") || (channels.includes("lexical") && channels.includes("semantic") && channels.indexOf("lexical") > channels.indexOf("semantic"))) return false;
  if (!positiveIntegerOrNull(r.lexical_rank) || !positiveIntegerOrNull(r.semantic_rank) || !boundedOrNull(r.lexical_signal) || !boundedOrNull(r.semantic_signal) || !nonNegativeOrNull(r.lexical_rrf_contribution) || !nonNegativeOrNull(r.semantic_rrf_contribution) || !nonNegativeOrNull(r.fused_rrf_score)) return false;
  if (r.mode === "lexical") return JSON.stringify(channels) === JSON.stringify(["lexical"]) && r.lexical_rank !== null && r.lexical_signal !== null && [r.semantic_rank, r.semantic_signal, r.lexical_rrf_contribution, r.semantic_rrf_contribution, r.fused_rrf_score].every(v => v === null);
  if (r.mode === "semantic") return JSON.stringify(channels) === JSON.stringify(["semantic"]) && r.semantic_rank !== null && r.semantic_signal !== null && [r.lexical_rank, r.lexical_signal, r.lexical_rrf_contribution, r.semantic_rrf_contribution, r.fused_rrf_score].every(v => v === null);
  if (![1, 2].includes(channels.length) || r.fused_rrf_score === null) return false;
  const lexical = channels.includes("lexical"); const semantic = channels.includes("semantic");
  return [r.lexical_rank, r.lexical_signal, r.lexical_rrf_contribution].every(v => (v !== null) === lexical) && [r.semantic_rank, r.semantic_signal, r.semantic_rrf_contribution].every(v => (v !== null) === semantic);
}
function isExplainedResult(value: unknown): value is ExplainedMemorySearchResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  return exactKeys(r, ["rank", "memory", "explanation"]) && Number.isInteger(r.rank) && (r.rank as number) > 0 && isMemory(r.memory) && isExplanation(r.explanation);
}

function isAnswer(value: unknown): value is AnswerRead {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  if (JSON.stringify(Object.keys(r).sort()) !== JSON.stringify(["answer", "answer_status", "citations", "search_mode"])) return false;
  if (!["answered", "insufficient_evidence"].includes(r.answer_status as string) || typeof r.answer !== "string" || !["lexical", "semantic", "hybrid"].includes(r.search_mode as string) || !Array.isArray(r.citations)) return false;
  return r.citations.every((value) => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const c = value as Record<string, unknown>;
    return JSON.stringify(Object.keys(c).sort()) === JSON.stringify(["label", "lexical_score", "memory", "rank", "semantic_score"]) &&
      typeof c.label === "string" && Number.isInteger(c.rank) && (c.rank as number) >= 1 && isMemory(c.memory) && score(c.lexical_score) && score(c.semantic_score);
  });
}

export function createAnswer(body: AnswerRequest, signal?: AbortSignal) {
  return request("/answers", isAnswer, signal, { method: "POST", body }, undefined, false, true);
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
export function searchMemories(mode: SearchMode, query: string, filters: MemorySearchFilters, limit: number, signal?: AbortSignal) {
  if (mode === "lexical") {
    const params = new URLSearchParams({ query, limit: String(limit), offset: "0" });
    Object.entries(filters).forEach(([key, value]) => { if (value !== undefined) params.set(key, String(value)); });
    return request(`/memories?${params}`, (v): v is MemoryRead[] => Array.isArray(v) && v.every(isMemory), signal, undefined, undefined, true);
  }
  return request("/memories/search", (v): v is MemoryRead[] => Array.isArray(v) && v.every(isMemory), signal, {
    method: "POST", body: { query, mode, filters, pagination: { limit, offset: 0 } },
  }, undefined, true);
}
export function searchMemoriesExplained(mode: SearchMode, query: string, filters: MemorySearchFilters, limit: number, signal?: AbortSignal) {
  const body: ExplainedMemorySearchRequest = { query, mode, filters, pagination: { limit, offset: 0 } };
  return request("/memories/search/explained", (v): v is ExplainedMemorySearchResult[] => Array.isArray(v) && v.every(isExplainedResult), signal, { method: "POST", body }, undefined, true);
}
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

const isCount = (value: unknown): value is number =>
  Number.isInteger(value) && (value as number) >= 0;

function isCountRecord(value: unknown): value is Record<string, number> {
  return typeof value === "object" && value !== null && !Array.isArray(value) &&
    Object.entries(value).every(([key, count]) => key.length > 0 && isCount(count));
}

function isOperationsDiagnostics(value: unknown): value is OperationsDiagnostics {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  const keys = ["aggregate_counts", "captured_at", "checks", "diagnostics_status", "failure_count", "warning_count"];
  if (JSON.stringify(Object.keys(r).sort()) !== JSON.stringify(keys.sort()) ||
      !["healthy", "unhealthy"].includes(r.diagnostics_status as string) ||
      !isTimestamp(r.captured_at) || !isCount(r.warning_count) || !isCount(r.failure_count) ||
      !isCountRecord(r.aggregate_counts) || !Array.isArray(r.checks)) return false;
  let previous = "";
  let warnings = 0;
  let failures = 0;
  for (const value of r.checks) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const check = value as Record<string, unknown>;
    if (JSON.stringify(Object.keys(check).sort()) !== JSON.stringify(["category", "check_id", "message", "status"]) ||
        typeof check.check_id !== "string" || typeof check.category !== "string" ||
        typeof check.message !== "string" || !["passed", "warning", "failed"].includes(check.status as string)) return false;
    const order = `${check.category}\u0000${check.check_id}`;
    if (order < previous) return false;
    previous = order;
    warnings += check.status === "warning" ? 1 : 0;
    failures += check.status === "failed" ? 1 : 0;
  }
  return warnings === r.warning_count && failures === r.failure_count &&
    r.diagnostics_status === (failures ? "unhealthy" : "healthy");
}

function isOperationsMaintenance(value: unknown): value is OperationsMaintenanceAudit {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  const keys = ["captured_at", "counts_by_status", "findings", "project_assigned_memories", "total_memories", "unassigned_memories"];
  if (JSON.stringify(Object.keys(r).sort()) !== JSON.stringify(keys.sort()) || !isTimestamp(r.captured_at) ||
      !isCount(r.total_memories) || !isCount(r.project_assigned_memories) || !isCount(r.unassigned_memories) ||
      (r.project_assigned_memories as number) + (r.unassigned_memories as number) !== r.total_memories ||
      !isCountRecord(r.counts_by_status) || !Array.isArray(r.findings)) return false;
  let previous = "";
  return r.findings.every((value) => {
    if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
    const finding = value as Record<string, unknown>;
    const valid = JSON.stringify(Object.keys(finding).sort()) === JSON.stringify(["count", "finding_id"]) &&
      typeof finding.finding_id === "string" && isCount(finding.count) && finding.finding_id >= previous;
    previous = typeof finding.finding_id === "string" ? finding.finding_id : previous;
    return valid;
  });
}

export function getOperationsDiagnostics(signal?: AbortSignal) {
  return request("/operations/diagnostics", isOperationsDiagnostics, signal);
}

export function getOperationsMaintenanceAudit(signal?: AbortSignal) {
  return request("/operations/maintenance-audit", isOperationsMaintenance, signal);
}

const IMPORT_KEYS = ["bundle_sha256", "entity_counts", "format_name", "format_version", "project_id", "project_name", "source_alembic_revision"];
function isImportBase(r: Record<string, unknown>): boolean {
  return typeof r.format_name === "string" && Number.isInteger(r.format_version) &&
    typeof r.project_id === "string" && UUID_PATTERN.test(r.project_id) && typeof r.project_name === "string" &&
    typeof r.source_alembic_revision === "string" && isCountRecord(r.entity_counts) &&
    typeof r.bundle_sha256 === "string" && /^[0-9a-f]{64}$/.test(r.bundle_sha256);
}
function isImportPlan(value: unknown): value is ProjectImportPlan {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>; const keys = [...IMPORT_KEYS, "conflict_count", "conflicts", "importable", "validation_status", "warning_count", "warnings"];
  return JSON.stringify(Object.keys(r).sort()) === JSON.stringify(keys.sort()) && r.validation_status === "valid" &&
    typeof r.importable === "boolean" && isImportBase(r) && Array.isArray(r.conflicts) && r.conflicts.every(v => typeof v === "string") &&
    Array.isArray(r.warnings) && r.warnings.every(v => typeof v === "string") && isCount(r.conflict_count) && isCount(r.warning_count) &&
    r.conflict_count === r.conflicts.length && r.warning_count === r.warnings.length && r.importable === (r.conflict_count === 0);
}
function isImportResult(value: unknown): value is ProjectImportResult {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  return JSON.stringify(Object.keys(r).sort()) === JSON.stringify([...IMPORT_KEYS, "import_status"].sort()) && r.import_status === "imported" && isImportBase(r);
}
async function rawOperation(path: string, file: File, operation: string, signal?: AbortSignal): Promise<Response> {
  try {
    return await fetch(`${apiBase()}${path}`, { method: "POST", headers: { Accept: "application/json", "Content-Type": "application/vnd.second-brain.project-export", "X-Second-Brain-Operation": operation }, body: file, signal, credentials: "same-origin" });
  } catch { throw new SafeApiError(); }
}
export async function exportProject(projectId: string, signal?: AbortSignal): Promise<ProjectExportDownload> {
  let response: Response;
  try { response = await fetch(`${apiBase()}/operations/project-exports/${projectId}`, { method: "POST", headers: { "X-Second-Brain-Operation": "project-export-v1" }, signal, credentials: "same-origin" }); }
  catch { throw new SafeApiError(); }
  if (!response.ok) throw new SafeApiError();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /^attachment; filename="?(project-[0-9a-f-]{36}\.sbexport)"?$/i.exec(disposition);
  if (!match || !/^project-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.sbexport$/i.test(match[1])) throw new SafeApiError();
  return { blob: await response.blob(), filename: match[1] };
}
export async function validateProjectImport(file: File, signal?: AbortSignal): Promise<ProjectImportPlan> {
  const response = await rawOperation("/operations/project-imports/validate", file, "project-import-validate-v1", signal);
  if (!response.ok) throw new SafeApiError();
  const value: unknown = await response.json(); if (!isImportPlan(value)) throw new SafeApiError(); return value;
}
export async function executeProjectImport(file: File, projectId: string, hash: string, signal?: AbortSignal): Promise<ProjectImportResult> {
  const query = new URLSearchParams({ expected_project_id: projectId, expected_bundle_sha256: hash });
  const response = await rawOperation(`/operations/project-imports/execute?${query}`, file, "project-import-execute-v1", signal);
  if (response.status === 409) throw new ImportConflictError();
  if (!response.ok) throw new SafeApiError();
  const value: unknown = await response.json(); if (!isImportResult(value)) throw new SafeApiError(); return value;
}
