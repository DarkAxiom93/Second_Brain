import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  AgentRunNotFoundError,
  ApiConflictError,
  cancelAgentRun,
  createAgentRun,
  executeAgentRun,
  getAgentExecution,
  getAgentPlan,
  getAgentRun,
  isProjectId,
  listAgentRuns,
  listApprovalRequests,
  planAgentRun,
  reviewApproval,
  type AgentExecution,
  type AgentPlan,
  type AgentRun,
  type ApprovalRequest,
} from "./api/client";

const stamp = (value: string | null) => value
  ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
  : "Not set";
const json = (value: unknown) => JSON.stringify(value, null, 2);
const cancellable = new Set(["created", "planning", "ready", "running", "awaiting_approval"]);
const validKind = (value: string) => value.length <= 100 && /^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$/.test(value);
const validVersion = (value: string) => value.length <= 50 && /^[A-Za-z0-9](?:[A-Za-z0-9._+-]*[A-Za-z0-9])?$/.test(value);

export function AgentRuns() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const [goal, setGoal] = useState("");
  const [agentChoice, setAgentChoice] = useState<"manual" | "research" | "memory_curator">("manual");
  const [kind, setKind] = useState("manual");
  const [version, setVersion] = useState("1");
  const [scope, setScope] = useState<"unassigned" | "project">("unassigned");
  const [project, setProject] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const goalRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const fixedIdentity = agentChoice !== "manual";

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    listAgentRuns(controller.signal)
      .then((value) => { setRuns(value); setState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => controller.abort();
  }, [attempt]);

  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const cleanGoal = goal.trim();
    if (!cleanGoal) {
      setMessage("Enter a goal summary.");
      goalRef.current?.focus();
      return;
    }
    if (!validKind(kind)) {
      setMessage("Enter a valid agent kind using lowercase letters, numbers, dots, underscores, or hyphens.");
      document.getElementById("agent-kind")?.focus();
      return;
    }
    if (!validVersion(version)) {
      setMessage("Enter a valid agent version using letters, numbers, dots, underscores, plus signs, or hyphens.");
      document.getElementById("agent-version")?.focus();
      return;
    }
    if (scope === "project" && !isProjectId(project)) {
      setMessage("Enter a valid Project UUID.");
      document.getElementById("agent-project")?.focus();
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const run = await createAgentRun({
        project_id: scope === "project" ? project : null,
        agent_kind: kind,
        agent_version: version,
        goal_summary: cleanGoal,
      });
      navigate(`/agents/${run.id}`);
    } catch {
      setMessage("The Run could not be created safely.");
      setBusy(false);
    }
  }

  const describedBy = message ? "run-form-error" : undefined;
  return <>
    <header className="page-header"><p className="eyebrow">Manual runtime</p><h1>Agent Runs</h1><p>Create and inspect bounded local Agent Runs.</p></header>
    <section className="panel" aria-labelledby="create-run">
      <h2 id="create-run">Create a Run</h2>
      <form noValidate onSubmit={submit}>
        <label htmlFor="agent-goal">Goal summary</label>
        <textarea ref={goalRef} id="agent-goal" maxLength={1000} aria-describedby={describedBy} value={goal} onChange={(event) => setGoal(event.target.value)} disabled={busy} />
        <label htmlFor="agent-choice">Agent choice</label>
        <select id="agent-choice" value={agentChoice} onChange={(event) => { const value = event.target.value as "manual" | "research" | "memory_curator"; setAgentChoice(value); setKind(value === "manual" ? "manual" : value); setVersion("1"); }} disabled={busy}>
          <option value="manual">Manual</option><option value="research">Research</option><option value="memory_curator">Memory Curator</option>
        </select>
        <label htmlFor="agent-kind">Agent kind</label>
        <input id="agent-kind" maxLength={100} aria-describedby={describedBy} value={kind} onChange={(event) => setKind(event.target.value)} disabled={busy || fixedIdentity} readOnly={fixedIdentity} />
        <label htmlFor="agent-version">Agent version</label>
        <input id="agent-version" maxLength={50} aria-describedby={describedBy} value={version} onChange={(event) => setVersion(event.target.value)} disabled={busy || fixedIdentity} readOnly={fixedIdentity} />
        <fieldset><legend>Scope</legend>
          <label><input type="radio" name="scope" checked={scope === "unassigned"} onChange={() => setScope("unassigned")} /> Explicitly unassigned</label>
          <label><input type="radio" name="scope" checked={scope === "project"} onChange={() => setScope("project")} /> Exact Project</label>
        </fieldset>
        {scope === "project" && <><label htmlFor="agent-project">Exact Project UUID</label><input id="agent-project" aria-describedby={describedBy} value={project} onChange={(event) => setProject(event.target.value.trim())} /></>}
        {message && <p id="run-form-error" className="field-error" role="alert">{message}</p>}
        <button disabled={busy} type="submit">{busy ? "Creating…" : "Create Run"}</button>
      </form>
    </section>
    <section className="panel" aria-labelledby="run-list" aria-busy={state === "loading"}>
      <div className="section-heading"><h2 id="run-list">Runs</h2><button type="button" onClick={refresh} disabled={state === "loading"}>Refresh Runs</button></div>
      <div aria-live="polite">
        {state === "loading" && <p>Loading Runs…</p>}
        {state === "error" && <p>Runs could not be loaded. Use Refresh to try again.</p>}
        {state === "ready" && runs.length === 0 && <p>No Agent Runs found.</p>}
        {state === "ready" && runs.length > 0 && <ol className="agent-list">{runs.map((run) => <li key={run.id}><h3><Link to={`/agents/${run.id}`}>{run.goal_summary}</Link></h3><p><span className="status-label">{run.state}</span> · {run.agent_kind} {run.agent_version}</p><p className="chunk-meta">Scope: {run.project_id ?? "Explicitly unassigned"} · Updated {stamp(run.updated_at)}</p></li>)}</ol>}
      </div>
    </section>
  </>;
}

export function AgentRunDetail() {
  const { runId = "" } = useParams();
  const valid = isProjectId(runId);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [execution, setExecution] = useState<AgentExecution | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error" | "missing" | "invalid">(valid ? "loading" : "invalid");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const refreshRef = useRef<HTMLButtonElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async (controller: AbortController) => {
    const current = await getAgentRun(runId, controller.signal);
    const [currentPlan, currentExecution, currentApprovals] = await Promise.all([
      current.state === "created" || current.state === "planning" ? Promise.resolve(null) : getAgentPlan(runId, controller.signal).catch(() => null),
      getAgentExecution(runId, controller.signal),
      listApprovalRequests(runId, controller.signal),
    ]);
    return { current, currentPlan, currentExecution, currentApprovals };
  }, [runId]);

  useEffect(() => {
    if (!valid) { setState("invalid"); return; }
    const controller = new AbortController();
    setState("loading");
    load(controller)
      .then(({ current, currentPlan, currentExecution, currentApprovals }) => {
        setRun(current); setPlan(currentPlan); setExecution(currentExecution); setApprovals(currentApprovals); setState("ready");
        window.setTimeout(() => headingRef.current?.focus(), 0);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState(error instanceof AgentRunNotFoundError ? "missing" : "error");
          window.setTimeout(() => headingRef.current?.focus(), 0);
        }
      });
    return () => controller.abort();
  }, [valid, attempt, load]);

  function conflict() {
    setMessage("This Run or Approval changed. Refresh before trying again.");
    window.setTimeout(() => refreshRef.current?.focus(), 0);
  }

  async function act(kind: "plan" | "execute" | "cancel") {
    if (!run || busy) return;
    setBusy(true); setMessage("");
    try {
      if (kind === "plan") { const value = await planAgentRun(run.id, run.revision); setPlan(value); setRun(value.run); }
      else if (kind === "execute") { const value = await executeAgentRun(run.id, run.revision); setExecution(value); setRun(value.run); }
      else { setRun(await cancelAgentRun(run.id, run.revision)); }
      setMessage(`${kind === "plan" ? "Planning" : kind === "execute" ? "Read-only execution" : "Cancellation"} completed.`);
      window.setTimeout(() => statusRef.current?.focus(), 0);
    } catch (error) {
      if (error instanceof ApiConflictError) conflict();
      else if (kind === "plan") {
        try {
          const current = await getAgentRun(run.id);
          setRun(current);
          if (current.state === "planning") {
            setMessage("Planning is still in progress on the server. Use Refresh Run to check again.");
          } else if (current.state === "ready") {
            const frozen = await getAgentPlan(run.id);
            setPlan(frozen); setRun(frozen.run); setMessage("Planning completed.");
          } else if (["failed", "cancelled", "expired"].includes(current.state)) {
            setMessage(`Planning ended safely with state ${current.state}.`);
          } else {
            setMessage("The planning request could not be completed safely.");
          }
        } catch {
          setMessage("The planning request was interrupted. Refresh Run to check its current state.");
        }
      } else if (kind === "execute") {
        try {
          const current = await getAgentExecution(run.id);
          setExecution(current); setRun(current.run);
          if (current.run.state === "running") {
            setMessage("Read-only execution is still in progress on the server. Use Refresh Run to check again.");
          } else if (current.run.state === "completed") {
            setMessage("Read-only execution completed.");
          } else if (["failed", "cancelled", "expired"].includes(current.run.state)) {
            setMessage(`Read-only execution ended safely with state ${current.run.state}.`);
          } else {
            setMessage("The execution request was interrupted. Refresh Run to check its current state.");
          }
        } catch {
          setMessage("The execution request was interrupted. Refresh Run to check its current state.");
        }
      } else setMessage("The action could not be completed safely.");
    } finally { setBusy(false); }
  }

  async function review(approval: ApprovalRequest, decision: "approve" | "reject") {
    const wording = `Confirm ${decision} for ${approval.action_type} targeting ${approval.target_type} ${approval.target_id}, frozen version ${approval.target_version}, risk ${approval.risk_classification}, expiring ${stamp(approval.expires_at)}? Preview: ${approval.preview}`;
    if (!window.confirm(wording)) return;
    setBusy(true); setMessage("");
    try {
      const updated = await reviewApproval(approval.id, decision);
      setApprovals((items) => items.map((item) => item.id === updated.id ? updated : item));
      setMessage(`Approval Request ${updated.status}. No action was executed.`);
      window.setTimeout(() => statusRef.current?.focus(), 0);
    } catch (error) {
      if (error instanceof ApiConflictError) conflict(); else setMessage("The review could not be completed safely.");
    } finally { setBusy(false); }
  }

  if (!valid || state === "invalid") return <section className="panel"><h1>Invalid Run address</h1><p>The Run identifier is malformed.</p></section>;
  return <>
    <header className="page-header"><p className="eyebrow">Agent Run detail</p><h1 ref={headingRef} tabIndex={-1}>{run?.goal_summary ?? "Agent Run"}</h1></header>
    <section className="panel" aria-live="polite" aria-busy={state === "loading"}>
      {state === "loading" && <p>Loading Run…</p>}
      {state === "missing" && <><h2>Run not found</h2><p>The requested Agent Run does not exist.</p><Link className="back-link" to="/agents">Back to Agent Runs</Link></>}
      {state === "error" && <><h2>Run unavailable</h2><p>The Run could not be loaded safely.</p><button ref={refreshRef} type="button" onClick={() => setAttempt((value) => value + 1)}>Refresh Run</button></>}
      {state === "ready" && run && <>
        <div ref={statusRef} tabIndex={-1}><strong>State: {run.state}</strong></div>
        {message && <p role="status">{message}</p>}
        <div className="actions"><button ref={refreshRef} type="button" disabled={busy} onClick={() => setAttempt((value) => value + 1)}>Refresh Run</button>{run.state === "created" && <button disabled={busy} type="button" onClick={() => act("plan")}>Start planning</button>}{run.state === "ready" && <button disabled={busy} type="button" onClick={() => act("execute")}>Start read-only execution</button>}{cancellable.has(run.state) && <button disabled={busy} type="button" onClick={() => act("cancel")}>Cancel Run</button>}</div>
        <dl className="detail-list"><div><dt>Agent</dt><dd>{run.agent_kind} · {run.agent_version}</dd></div><div><dt>Scope</dt><dd>{run.project_id ? <>Exact Project <Link to={`/projects/${run.project_id}`}>{run.project_id}</Link></> : "Explicitly unassigned"}</dd></div><div><dt>Revision</dt><dd>{run.revision}</dd></div><div><dt>Policy / registry</dt><dd>{run.policy_version} / {run.registry_version}</dd></div><div><dt>Budgets</dt><dd>{run.step_budget} steps · {run.tool_call_budget} calls · {run.retry_budget} retry</dd></div><div><dt>Planning / Run deadline</dt><dd>{stamp(run.planning_deadline)} / {stamp(run.run_deadline)}</dd></div><div><dt>Created / updated / started / finished</dt><dd>{stamp(run.created_at)} / {stamp(run.updated_at)} / {stamp(run.started_at)} / {stamp(run.finished_at)}</dd></div><div><dt>Safe status code</dt><dd>{run.safe_error_code ?? "None"}</dd></div></dl>
        <section aria-labelledby="plan-heading"><h2 id="plan-heading">Plan and Steps</h2>{!plan ? <p>No frozen plan is available.</p> : <ol className="agent-list">{[...plan.steps].sort((a, b) => a.ordinal - b.ordinal).map((step) => <li key={step.ordinal}><h3>Step {step.ordinal + 1}: {step.purpose}</h3><p>{step.tool_name} version {step.tool_version}</p><details><summary>Bounded input and conditions</summary><pre className="evidence">{json(step.normalized_input)}</pre><p>Expected evidence: {step.expected_evidence.join(", ") || "None"}</p><p>Success: {step.success_condition}</p><p>Stop: {step.stop_condition}</p></details></li>)}</ol>}</section>
        <section aria-labelledby="execution-heading"><h2 id="execution-heading">Execution</h2>{!execution || execution.steps.length === 0 ? <p>No execution results.</p> : <ol className="agent-list">{[...execution.steps].sort((a, b) => a.ordinal - b.ordinal).map((step) => <li key={step.ordinal}><h3>Step {step.ordinal + 1}: {step.status}</h3><p>{step.safe_result_summary ?? "No safe result summary."}</p>{step.safe_error_code && <p>Safe status code: {step.safe_error_code}</p>}{step.evidence_references.length > 0 && <><h4>Evidence references</h4><ul>{step.evidence_references.map((evidence, index) => <li key={index}><code>{json(evidence)}</code></li>)}</ul></>}</li>)}</ol>}</section>
        {run.agent_kind === "research" && <section aria-labelledby="research-heading"><h2 id="research-heading">Research result</h2>{!execution?.research_result ? <p>No Research result is available.</p> : <><p><strong>Status: {execution.research_result.status === "answered" ? "Answered" : "Insufficient evidence"}</strong></p>{execution.research_result.insufficiency && <p>{execution.research_result.insufficiency}</p>}{execution.research_result.claims.length > 0 && <ol className="agent-list">{execution.research_result.claims.map((claim, index) => <li key={index}><p>{claim.text}</p><p>Citations: {claim.citation_numbers.map((number) => `[${number}]`).join(" ")}</p></li>)}</ol>}{execution.research_result.citations.length > 0 && <ol>{execution.research_result.citations.map((citation) => <li key={citation.number}><code>{citation.entity_type} {citation.entity_id} · version {citation.version}</code></li>)}</ol>}</>}</section>}
        {run.agent_kind === "memory_curator" && <section aria-labelledby="curator-heading"><h2 id="curator-heading">Curator advice</h2>{!execution?.curator_result ? <p>No Curator result is available.</p> : <><h3>Advisory findings</h3>{execution.curator_result.findings.length === 0 ? <p>No findings.</p> : <ol className="agent-list">{execution.curator_result.findings.map((finding, index) => <li key={index}><p>{finding.text}</p>{finding.evidence.map((item) => <code key={`${item.entity_type}-${item.entity_id}`}>{item.entity_type} {item.entity_id} · version {item.version}</code>)}</li>)}</ol>}<h3>Proposed actions</h3>{execution.curator_result.proposed_actions.length === 0 ? <p>No proposed actions.</p> : <ol>{execution.curator_result.proposed_actions.map((item) => <li key={item.approval_id}><code>{item.action_type} · Memory {item.target_id} · frozen version {item.target_version}</code></li>)}</ol>}</>}</section>}
        {run.agent_kind !== "research" && <section aria-labelledby="approval-heading"><h2 id="approval-heading">Approval Requests</h2>{approvals.length === 0 ? <p>No Approval Requests.</p> : <ol className="agent-list">{approvals.map((approval) => <li key={approval.id}><h3>{approval.action_type} · <span className="status-label">{approval.status}</span></h3><p>Target: {approval.target_type} {approval.target_id} · frozen version {approval.target_version}</p><p>Risk: {approval.risk_classification} · Created: {stamp(approval.created_at)} · Expires: {stamp(approval.expires_at)} · Reviewed: {stamp(approval.reviewed_at)}</p><p className="evidence"><strong>Safe preview:</strong> {approval.preview}</p><details><summary>Normalized proposed input and evidence</summary><pre className="evidence">{json(approval.proposed_input)}</pre>{approval.evidence_references.map((evidence, index) => <code key={index}>{json(evidence)}</code>)}</details>{approval.status === "pending" && <div className="actions"><button disabled={busy} type="button" onClick={() => review(approval, "approve")}>Approve exact proposal</button><button disabled={busy} type="button" onClick={() => review(approval, "reject")}>Reject exact proposal</button></div>}</li>)}</ol>}</section>}
        {run.agent_kind === "daily_brief" && <section aria-labelledby="daily-brief-heading"><h2 id="daily-brief-heading">Daily Brief</h2>{!execution?.daily_brief_result ? <p>No Daily Brief result is available.</p> : <><p><strong>Status: {execution.daily_brief_result.status === "answered" ? "Brief available" : "Insufficient evidence"}</strong></p>{execution.daily_brief_result.insufficiency && <p>{execution.daily_brief_result.insufficiency}</p>}{execution.daily_brief_result.claims.length > 0 && <ol className="agent-list">{execution.daily_brief_result.claims.map((claim, index) => <li key={index}><p>{claim.text}</p><p>Citations: {claim.citation_numbers.map((number) => `[${number}]`).join(" ")}</p></li>)}</ol>}{execution.daily_brief_result.citations.length > 0 && <ol>{execution.daily_brief_result.citations.map((citation) => <li key={citation.number}><code>{citation.entity_type} {citation.entity_id} · version {citation.version}</code></li>)}</ol>}</>}</section>}
        <Link className="back-link" to="/agents">Back to Agent Runs</Link>
      </>}
    </section>
  </>;
}
