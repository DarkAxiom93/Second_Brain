import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentRunDetail, AgentRuns } from "./Agents";

const id = "11111111-1111-4111-8111-111111111111";
const project = "22222222-2222-4222-8222-222222222222";
const approvalId = "33333333-3333-4333-8333-333333333333";
const target = "44444444-4444-4444-8444-444444444444";
const now = "2026-08-19T08:00:00Z";

const run = (state = "created", extra: Record<string, unknown> = {}) => ({
  id, project_id: null, agent_kind: "manual", agent_version: "1",
  goal_summary: "Review local evidence", registry_version: "agent-tools-v1",
  policy_version: "agent-policy-v1", state, step_budget: 12,
  tool_call_budget: 20, retry_budget: 1, planning_deadline: now,
  run_deadline: now, revision: 0, safe_error_code: null, created_at: now,
  updated_at: now, started_at: null, finished_at: null, ...extra,
});
const execution = (value = run()) => ({ run: value, steps: [] });
const approval = (status = "pending", extra: Record<string, unknown> = {}) => ({
  id: approvalId, run_id: id, step_ordinal: 0, action_type: "memory.update",
  target_type: "memory", target_id: target, target_version: "v7",
  proposed_input: { summary: "bounded" }, preview: "Change the safe summary",
  evidence_references: [{ type: "memory", id: target }],
  risk_classification: "medium", status, created_at: now, expires_at: now,
  reviewed_at: null, ...extra,
});
const response = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body),
}) as unknown as Response;

function renderList() {
  return render(<MemoryRouter><AgentRuns /></MemoryRouter>);
}
function renderDetail() {
  return render(<MemoryRouter initialEntries={[`/agents/${id}`]}><Routes><Route path="/agents/:runId" element={<AgentRunDetail />} /></Routes></MemoryRouter>);
}
function detailFetch(value = run(), approvals: unknown[] = []) {
  return vi.fn((url: string) => Promise.resolve(response(
    url.includes("approval-requests") ? approvals
      : url.endsWith("/execution") ? execution(value)
        : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] }
          : value,
  )));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("Agent Runs list and creation", () => {
  it("renders loading, empty, manual refresh, and never polls or persists", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([]));
    vi.stubGlobal("fetch", fetchMock);
    renderList();
    expect(screen.getByText("Loading Runs…")).toBeInTheDocument();
    expect(await screen.findByText("No Agent Runs found.")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Refresh Runs" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("renders a successful bounded list with a keyboard-operable detail link", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response([run("ready", { project_id: project })])));
    renderList();
    const link = await screen.findByRole("link", { name: "Review local evidence" });
    expect(link).toHaveAttribute("href", `/agents/${id}`);
    await userEvent.tab();
    while (document.activeElement !== link) await userEvent.tab();
    expect(link).toHaveFocus();
    expect(screen.getByText(new RegExp(`Scope: ${project}`))).toBeInTheDocument();
  });

  it("shows a safe list error without exposing the response body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "SQL secret" }, 500)));
    renderList();
    expect(await screen.findByText(/could not be loaded/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("SQL secret");
  });

  it("associates validation errors and focuses the invalid field without a request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([]));
    vi.stubGlobal("fetch", fetchMock);
    renderList();
    await screen.findByText("No Agent Runs found.");
    await userEvent.click(screen.getByRole("button", { name: "Create Run" }));
    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent("Enter a goal summary");
    expect(screen.getByLabelText("Goal summary")).toHaveFocus();
    expect(screen.getByLabelText("Goal summary")).toHaveAttribute("aria-describedby", error.id);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("creates exact unassigned and Project scopes without automatic planning", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response([])).mockResolvedValueOnce(response(run(), 201))
      .mockResolvedValueOnce(response([])).mockResolvedValueOnce(response(run("created", { project_id: project }), 201));
    vi.stubGlobal("fetch", fetchMock);
    const first = renderList();
    await screen.findByText("No Agent Runs found.");
    expect(screen.getByLabelText("Explicitly unassigned")).toBeChecked();
    await userEvent.type(screen.getByLabelText("Goal summary"), "Review local evidence");
    await userEvent.click(screen.getByRole("button", { name: "Create Run" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    let init = fetchMock.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({ project_id: null, agent_kind: "manual", agent_version: "1", goal_summary: "Review local evidence" });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/plan"))).toBe(false);
    first.unmount();
    renderList();
    await screen.findByText("No Agent Runs found.");
    await userEvent.type(screen.getByLabelText("Goal summary"), "Project goal");
    await userEvent.click(screen.getByLabelText("Exact Project"));
    await userEvent.type(screen.getByLabelText("Exact Project UUID"), project);
    await userEvent.click(screen.getByRole("button", { name: "Create Run" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    init = fetchMock.mock.calls[3][1] as RequestInit;
    expect(JSON.parse(init.body as string).project_id).toBe(project);
  });

  it("selects fixed Research version 1 while preserving editable Manual identity", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response([])).mockResolvedValueOnce(
      response(run("created", { agent_kind: "research" }), 201),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderList();
    await screen.findByText("No Agent Runs found.");
    expect(screen.getByLabelText("Agent kind")).not.toHaveAttribute("readonly");
    await userEvent.selectOptions(screen.getByLabelText("Agent choice"), "research");
    expect(screen.getByLabelText("Agent kind")).toHaveValue("research");
    expect(screen.getByLabelText("Agent kind")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Agent version")).toHaveValue("1");
    expect(screen.getByLabelText("Agent version")).toHaveAttribute("readonly");
    await userEvent.type(screen.getByLabelText("Goal summary"), "Cited local answer");
    await userEvent.click(screen.getByRole("button", { name: "Create Run" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const body = JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string);
    expect(body).toMatchObject({ agent_kind: "research", agent_version: "1" });
  });
});

describe("Agent Run detail", () => {
  it("renders every public state and the exact action matrix", async () => {
    for (const state of ["created", "planning", "ready", "running", "awaiting_approval", "completed", "failed", "cancelled", "expired"]) {
      cleanup();
      vi.stubGlobal("fetch", detailFetch(run(state)));
      renderDetail();
      expect(await screen.findByText(`State: ${state}`)).toBeInTheDocument();
      expect(Boolean(screen.queryByRole("button", { name: "Start planning" }))).toBe(state === "created");
      expect(Boolean(screen.queryByRole("button", { name: "Start read-only execution" }))).toBe(state === "ready");
      expect(Boolean(screen.queryByRole("button", { name: "Cancel Run" }))).toBe(["created", "planning", "ready", "running", "awaiting_approval"].includes(state));
      expect(screen.getByRole("button", { name: "Refresh Run" })).toBeEnabled();
    }
  });

  it("supports a direct deep-link and distinguishes not found from safe unavailable", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ detail: "agent run not found" }, 404));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Run not found" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("agent run not found");
    expect(screen.getByRole("heading", { name: "Agent Run" })).toHaveFocus();
    cleanup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "postgresql://secret" }, 503)));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Run unavailable" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("postgresql");
    expect(screen.getByRole("button", { name: "Refresh Run" })).toBeInTheDocument();
  });

  it("renders ordered plans and bounded evidence as inert text", async () => {
    const value = run("completed");
    const plan = { run: value, goal_summary: value.goal_summary, steps: [
      { ordinal: 1, purpose: "Second", tool_name: "memory.get", tool_version: 1, normalized_input: { id: target }, expected_evidence: ["memory"], success_condition: "found", stop_condition: "missing" },
      { ordinal: 0, purpose: "First", tool_name: "project.get", tool_version: 1, normalized_input: { id: project }, expected_evidence: [], success_condition: "found", stop_condition: "missing" },
    ] };
    const currentExecution = { run: value, steps: [{ ordinal: 0, purpose: "First", tool_name: "project.get", tool_version: 1, status: "succeeded", invocation_status: "succeeded", safe_result_summary: "<script>Project found</script>", evidence_references: [{ type: "project", id: project }], safe_error_code: null }] };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(url.endsWith("/plan") ? plan : url.endsWith("/execution") ? currentExecution : url.includes("approval-requests") ? [] : value))));
    renderDetail();
    const headings = await screen.findAllByRole("heading", { level: 3 });
    expect(headings.map((heading) => heading.textContent).slice(0, 2)).toEqual(["Step 1: First", "Step 2: Second"]);
    expect(screen.getByText("<script>Project found</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getAllByText(new RegExp(project))).toHaveLength(2);
  });

  it("uses exact revisions for plan, execute, and cancel without predicting success", async () => {
    for (const [state, label, suffix] of [["created", "Start planning", "/plan"], ["ready", "Start read-only execution", "/execute"], ["running", "Cancel Run", "/cancel"]] as const) {
      cleanup();
      const value = run(state, { revision: 9 });
      let resolveMutation: (result: Response) => void = () => undefined;
      const fetchMock = vi.fn((url: string, init?: RequestInit) => init?.method === "POST"
        ? new Promise<Response>((resolve) => { resolveMutation = resolve; })
        : Promise.resolve(response(url.includes("approval-requests") ? [] : url.endsWith("/execution") ? execution(value) : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] } : value)));
      vi.stubGlobal("fetch", fetchMock);
      renderDetail();
      await screen.findByText(`State: ${state}`);
      await userEvent.click(screen.getByRole("button", { name: label }));
      expect(screen.queryByText(/completed\./)).not.toBeInTheDocument();
      const call = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST")!;
      expect(call[0]).toContain(suffix);
      expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({ expected_revision: 9 });
      resolveMutation(response(suffix === "/cancel" ? run("cancelled", { revision: 10 }) : suffix === "/plan" ? { run: run("ready", { revision: 10 }), goal_summary: "Review local evidence", steps: [] } : execution(run("completed", { revision: 10 }))));
      expect(await screen.findByText(/completed\./)).toBeInTheDocument();
      await waitFor(() => expect(screen.getByText(/State:/).parentElement).toHaveFocus());
    }
  });

  it("handles mutation conflicts without success, retry, or optimistic overwrite", async () => {
    const value = run("created");
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? response({}, 409) : response(url.includes("approval-requests") ? [] : url.endsWith("/execution") ? execution(value) : value)));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    await screen.findByText("State: created");
    await userEvent.click(screen.getByRole("button", { name: "Start planning" }));
    expect(await screen.findByText(/changed.*Refresh/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh Run" })).toHaveFocus());
    expect(screen.getByText("State: created")).toBeInTheDocument();
    expect(screen.queryByText("Planning completed.")).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit)?.method === "POST")).toHaveLength(1);
  });

  it("confirms and approves one exact pending proposal without executing", async () => {
    const value = run("awaiting_approval");
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? response(approval("approved")) : response(url.includes("approval-requests") ? [approval()] : url.endsWith("/execution") ? execution(value) : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] } : value)));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    await screen.findByText(/Change the safe summary/);
    await userEvent.click(screen.getByRole("button", { name: "Approve exact proposal" }));
    const confirmation = confirm.mock.calls[0][0];
    for (const part of ["approve", "memory.update", target, "v7", "medium", "expiring", "Change the safe summary"]) expect(confirmation).toContain(part);
    const mutation = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST")!;
    expect(mutation[0]).toBe(`/api/approval-requests/${approvalId}/review`);
    expect(JSON.parse((mutation[1] as RequestInit).body as string)).toEqual({ decision: "approve" });
    expect(await screen.findByText(/approved.*No action was executed/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/execute"))).toHaveLength(0);
  });

  it("rejects exactly and canceling confirmation sends no mutation", async () => {
    const value = run("awaiting_approval");
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? response(approval("rejected")) : response(url.includes("approval-requests") ? [approval()] : url.endsWith("/execution") ? execution(value) : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] } : value)));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    const reject = await screen.findByRole("button", { name: "Reject exact proposal" });
    await userEvent.click(reject);
    expect(fetchMock.mock.calls.filter(([, init]) => (init as RequestInit)?.method === "POST")).toHaveLength(0);
    expect(reject).toHaveFocus();
    await userEvent.click(reject);
    const mutation = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST")!;
    expect(JSON.parse((mutation[1] as RequestInit).body as string)).toEqual({ decision: "reject" });
    expect(confirm.mock.calls[1][0]).toContain("Confirm reject");
    expect(await screen.findByText(/rejected.*No action was executed/)).toBeInTheDocument();
  });

  it("makes terminal Approvals non-actionable and communicates status in text", async () => {
    const value = run("completed");
    vi.stubGlobal("fetch", detailFetch(value, ["approved", "rejected", "expired", "superseded"].map((status, index) => approval(status, { id: `${index + 3}3333333-3333-4333-8333-333333333333` }))));
    renderDetail();
    await screen.findByText("No execution results.");
    for (const status of ["approved", "rejected", "expired", "superseded"]) expect(screen.getByText(status)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /exact proposal/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /execute|apply/i })).not.toBeInTheDocument();
  });

  it("handles review conflict without replacing the pending Approval", async () => {
    const value = run("awaiting_approval");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? response({ detail: "expired secret" }, 409) : response(url.includes("approval-requests") ? [approval()] : url.endsWith("/execution") ? execution(value) : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] } : value)));
    vi.stubGlobal("fetch", fetchMock);
    renderDetail();
    await userEvent.click(await screen.findByRole("button", { name: "Approve exact proposal" }));
    expect(await screen.findByText(/changed.*Refresh/)).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("expired secret");
    await waitFor(() => expect(screen.getByRole("button", { name: "Refresh Run" })).toHaveFocus());
  });

  it("rejects malformed projections containing private fields", async () => {
    const privateRun = { ...run(), correlation_hash: "private-correlation" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(privateRun)));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Run unavailable" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("private-correlation");
    cleanup();
    const value = run("awaiting_approval");
    const privateApproval = { ...approval(), proposal_hash: "private-proposal-hash", execution_identity: "private-execution" };
    vi.stubGlobal("fetch", detailFetch(value, [privateApproval]));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Run unavailable" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("private-proposal-hash");
    expect(document.body).not.toHaveTextContent("private-execution");
  });

  it("uses semantic responsive structures with live status and no keyboard trap", async () => {
    const value = run("awaiting_approval");
    vi.stubGlobal("fetch", detailFetch(value, [approval()]));
    renderDetail();
    await screen.findByText("State: awaiting_approval");
    expect(screen.getByRole("heading", { name: "Plan and Steps" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Execution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Approval Requests" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh Run" }).closest(".actions")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Approve exact proposal" }).closest(".actions")).not.toBeNull();
    expect(screen.getByText("State: awaiting_approval").closest("section")).toHaveAttribute("aria-live", "polite");
    const buttons = within(document.body).getAllByRole("button");
    expect(buttons.every((button) => button.tabIndex >= 0)).toBe(true);
  });

  it("renders bounded Research claims and safe ordered citation identities only", async () => {
    const value = run("completed", { agent_kind: "research", agent_version: "1" });
    const result = {
      run: value,
      steps: [],
      research_result: {
        status: "answered",
        claims: [{ text: "Supported local claim", citation_numbers: [1] }],
        citations: [{ number: 1, entity_type: "memory", entity_id: target, version: "a".repeat(64) }],
        insufficiency: null,
      },
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(
      url.includes("approval-requests") ? []
        : url.endsWith("/execution") ? result
          : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] }
            : value,
    ))));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Research result" })).toBeInTheDocument();
    expect(screen.getByText("Status: Answered")).toBeInTheDocument();
    expect(screen.getByText("Supported local claim")).toBeInTheDocument();
    expect(screen.getByText("Citations: [1]")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`memory ${target}`))).toHaveTextContent(`version ${"a".repeat(64)}`);
    expect(screen.queryByRole("heading", { name: "Approval Requests" })).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("raw provider");
  });

  it("renders safe Research insufficiency without claims, citations, or raw content", async () => {
    const value = run("completed", { agent_kind: "research", agent_version: "1" });
    const result = {
      run: value,
      steps: [],
      research_result: {
        status: "insufficient_evidence",
        claims: [],
        citations: [],
        insufficiency: "No local evidence supports a safe answer.",
      },
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(
      url.includes("approval-requests") ? []
        : url.endsWith("/execution") ? result
          : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] }
            : value,
    ))));
    renderDetail();
    expect(await screen.findByText("Status: Insufficient evidence")).toBeInTheDocument();
    expect(screen.getByText("No local evidence supports a safe answer.")).toBeInTheDocument();
    expect(screen.queryByText(/Citations:/)).not.toBeInTheDocument();
  });

  it("rejects Research projections containing private citation identities", async () => {
    const value = run("completed", { agent_kind: "research", agent_version: "1" });
    const privateResult = {
      run: value,
      steps: [],
      research_result: {
        status: "answered",
        claims: [{ text: "Claim", citation_numbers: [1] }],
        citations: [{ number: 1, entity_type: "memory", entity_id: target, version: "a".repeat(64), invocation_id: "private-invocation" }],
        insufficiency: null,
      },
    };
    vi.stubGlobal("fetch", vi.fn((url: string) => Promise.resolve(response(
      url.includes("approval-requests") ? []
        : url.endsWith("/execution") ? privateResult
          : url.endsWith("/plan") ? { run: value, goal_summary: value.goal_summary, steps: [] }
            : value,
    ))));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Run unavailable" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("private-invocation");
  });
});
