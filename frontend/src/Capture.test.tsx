import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { editCapture, SafeApiError } from "./api/client";

const projectId = "11111111-1111-4111-8111-111111111111";
const captureId = "22222222-2222-4222-8222-222222222222";
const sourceId = "33333333-3333-4333-8333-333333333333";
const projects = [{ id: projectId, name: "Alpha", description: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" }];
const item = (overrides = {}) => ({ id: captureId, project_id: null, content: "plain note", state: "pending", revision: 1, created_at: "2026-09-19T08:00:00Z", updated_at: "2026-09-19T08:00:00Z", processed_at: null, resulting_source_id: null, ...overrides });
const source = { id: sourceId, source_type: "capture", name: "Capture source", reference: null, checksum: "a".repeat(64), created_at: "2026-09-19T08:00:00Z", updated_at: "2026-09-19T08:00:00Z" };
function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response; }
function body(call: unknown[]) { return JSON.parse((call[1] as RequestInit).body as string) as Record<string, unknown>; }
function inboxFetch(items = [item()], cursor: string | null = null) { return vi.fn(async (url: string) => url.includes("/projects?") ? response(projects) : url.endsWith("/capture-items/query") ? response({ items, next_cursor: cursor }) : url.endsWith("/detail") ? response(items[0]) : response({})); }
function renderInbox(fetchMock = inboxFetch()) { vi.stubGlobal("fetch", fetchMock); return { fetchMock, ...render(<MemoryRouter initialEntries={["/inbox"]}><App /></MemoryRouter>) }; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

describe("Checkpoint 120 capture UI", () => {
  it("provides persistent navigation and an accessible focus-trapped Unassigned modal", async () => {
    const fetchMock = vi.fn(async (url: string) => url.includes("/projects?") ? response(projects) : response({ items: [], next_cursor: null })); vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/settings"]}><App /></MemoryRouter>); const launcher = screen.getByRole("button", { name: "+ Capture" }); launcher.focus(); await userEvent.click(launcher);
    const dialog = screen.getByRole("dialog", { name: "Quick Capture" }); expect(dialog).toHaveAttribute("aria-modal", "true"); expect(screen.getByLabelText("Capture text")).toHaveFocus(); expect(screen.getByLabelText("Exact scope")).toHaveValue("unassigned"); expect(within(dialog).queryByRole("option", { name: /all projects/i })).not.toBeInTheDocument();
    await userEvent.tab({ shift: true }); expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus(); await userEvent.tab(); expect(screen.getByLabelText("Capture text")).toHaveFocus(); await userEvent.tab({ shift: true }); expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus(); await userEvent.keyboard("{Escape}"); expect(dialog).not.toBeInTheDocument(); await waitFor(() => expect(launcher).toHaveFocus());
  });

  it("uses an application-local shortcut and ignores editable and composing targets", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => url.includes("/projects?") ? response(projects) : response({ items: [], next_cursor: null })));
    render(<MemoryRouter initialEntries={["/inbox"]}><App /></MemoryRouter>); await screen.findByLabelText("Lexical search");
    const suppress = (element: HTMLElement) => { element.dispatchEvent(new KeyboardEvent("keydown", { key: "c", ctrlKey: true, shiftKey: true, bubbles: true })); expect(screen.queryByRole("dialog")).not.toBeInTheDocument(); };
    suppress(screen.getByLabelText("Lexical search")); suppress(screen.getByLabelText("State"));
    const textarea = document.createElement("textarea"); document.body.append(textarea); suppress(textarea);
    const editable = document.createElement("div"); editable.contentEditable = "true"; const child = document.createElement("span"); editable.append(child); document.body.append(editable); suppress(editable); suppress(child); textarea.remove(); editable.remove();
    const composing = new KeyboardEvent("keydown", { key: "c", ctrlKey: true, shiftKey: true, bubbles: true }); Object.defineProperty(composing, "isComposing", { value: true }); document.dispatchEvent(composing); expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    (document.activeElement as HTMLElement).blur(); await userEvent.keyboard("{Control>}{Shift>}c{/Shift}{/Control}"); expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("reuses and rotates private idempotency keys by logical submission and announces success after close", async () => {
    const calls: unknown[][] = []; let createCount = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => { if (url.includes("/projects?")) return response(projects); if (url.endsWith("/capture-items")) { calls.push([url, init]); createCount += 1; if (createCount < 4) throw new TypeError("network"); return response(item({ content: "changed", project_id: createCount === 4 ? projectId : null }), 201); } return response({ items: [], next_cursor: null }); }); vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={["/inbox"]}><App /></MemoryRouter>); await userEvent.click(screen.getByRole("button", { name: "+ Capture" })); const text = screen.getByLabelText("Capture text"); await userEvent.type(text, "draft"); await userEvent.click(screen.getByRole("button", { name: "Save capture" })); await screen.findByText(/Retry the unchanged/); await userEvent.click(screen.getByRole("button", { name: "Save capture" })); await screen.findByText(/Retry the unchanged/);
    const firstKey = ((calls[0][1] as RequestInit).headers as Record<string,string>)["Idempotency-Key"]; const secondKey = ((calls[1][1] as RequestInit).headers as Record<string,string>)["Idempotency-Key"]; expect(secondKey).toBe(firstKey); expect(document.body).not.toHaveTextContent(firstKey);
    await userEvent.type(text, " changed"); await userEvent.click(screen.getByRole("button", { name: "Save capture" })); await waitFor(() => expect(calls).toHaveLength(3)); const contentKey = ((calls[2][1] as RequestInit).headers as Record<string,string>)["Idempotency-Key"]; expect(contentKey).not.toBe(firstKey);
    await userEvent.selectOptions(within(screen.getByRole("dialog")).getByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Save capture" })); await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument()); const scopeKey = ((calls[3][1] as RequestInit).headers as Record<string,string>)["Idempotency-Key"]; expect(scopeKey).not.toBe(contentKey); expect(body(calls[3])).toEqual({ content: "draft changed", project_id: projectId }); expect(screen.getByText("Capture saved.")).toBeInTheDocument(); await waitFor(() => expect(screen.getByRole("button", { name: "+ Capture" })).toHaveFocus());
    await userEvent.click(screen.getByRole("button", { name: "+ Capture" })); await userEvent.type(screen.getByLabelText("Capture text"), "next capture"); await userEvent.click(screen.getByRole("button", { name: "Save capture" })); await waitFor(() => expect(calls).toHaveLength(5)); const nextKey = ((calls[4][1] as RequestInit).headers as Record<string,string>)["Idempotency-Key"]; expect(nextKey).not.toBe(scopeKey); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });

  it("binds browse/search/pagination to exact scope and does not request on search editing", async () => {
    const { fetchMock } = renderInbox(inboxFetch([item()], "opaque-cursor")); await screen.findByText("plain note"); const baseline = fetchMock.mock.calls.length; await userEvent.type(screen.getByLabelText("Lexical search"), "needle"); expect(fetchMock).toHaveBeenCalledTimes(baseline);
    await userEvent.click(screen.getByRole("button", { name: "Search" })); await waitFor(() => expect(fetchMock.mock.calls.length).toBe(baseline + 1)); const queryCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith("/capture-items/query")); expect(body(queryCalls.at(-1)!)).toEqual({ scope: { unassigned: true }, states: ["pending"], page_size: 25, query: "needle" });
    await userEvent.click(screen.getByRole("button", { name: "Next page" })); await waitFor(() => expect(fetchMock.mock.calls.length).toBe(baseline + 2)); expect(body(fetchMock.mock.calls.at(-1)!)).toMatchObject({ scope: { unassigned: true }, states: ["pending"], query: "needle", cursor: "opaque-cursor" }); expect(document.body).not.toHaveTextContent("opaque-cursor");
  });

  it("invalidates cursors for scope, state, submitted query, and Clear changes", async () => {
    const requests: Array<{ body: Record<string, unknown>; resolve: (value: Response) => void }> = [];
    const fetchMock = vi.fn((url: string, init?: RequestInit) => url.includes("/projects?") ? Promise.resolve(response(projects)) : new Promise<Response>(resolve => requests.push({ body: body([url, init!]), resolve })));
    renderInbox(fetchMock); await waitFor(() => expect(requests).toHaveLength(1)); requests[0].resolve(response({ items: [item()], next_cursor: "cursor-1" })); await screen.findByRole("button", { name: "Next page" });
    await userEvent.selectOptions(screen.getByLabelText("Exact scope"), projectId); expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument(); await waitFor(() => expect(requests).toHaveLength(2)); expect(requests[1].body).not.toHaveProperty("cursor"); requests[1].resolve(response({ items: [item({ project_id: projectId })], next_cursor: "cursor-2" })); await screen.findByRole("button", { name: "Next page" });
    await userEvent.selectOptions(screen.getByLabelText("State"), "discarded"); expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument(); await waitFor(() => expect(requests).toHaveLength(3)); expect(requests[2].body).not.toHaveProperty("cursor"); requests[2].resolve(response({ items: [item({ project_id: projectId, state: "discarded" })], next_cursor: "cursor-3" })); await screen.findByRole("button", { name: "Next page" });
    await userEvent.type(screen.getByLabelText("Lexical search"), "new query"); await userEvent.click(screen.getByRole("button", { name: "Search" })); expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument(); await waitFor(() => expect(requests).toHaveLength(4)); expect(requests[3].body).toMatchObject({ query: "new query" }); expect(requests[3].body).not.toHaveProperty("cursor"); requests[3].resolve(response({ items: [], next_cursor: "cursor-4" })); await screen.findByRole("button", { name: "Next page" });
    await userEvent.click(screen.getByRole("button", { name: "Clear search" })); expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument(); await waitFor(() => expect(requests).toHaveLength(5)); expect(requests[4].body).not.toHaveProperty("query"); expect(requests[4].body).not.toHaveProperty("cursor"); requests[4].resolve(response({ items: [], next_cursor: null }));
  });

  it("fences an older delayed page so it cannot overwrite a newer exact view", async () => {
    const requests: Array<{ body: Record<string, unknown>; resolve: (value: Response) => void }> = [];
    const fetchMock = vi.fn((url: string, init?: RequestInit) => url.includes("/projects?") ? Promise.resolve(response(projects)) : new Promise<Response>(resolve => requests.push({ body: body([url, init!]), resolve })));
    renderInbox(fetchMock); await waitFor(() => expect(requests).toHaveLength(1)); requests[0].resolve(response({ items: [item({ content: "initial" })], next_cursor: "old-cursor" })); await screen.findByText("initial");
    await userEvent.click(screen.getByRole("button", { name: "Next page" })); await waitFor(() => expect(requests).toHaveLength(2)); await userEvent.selectOptions(screen.getByLabelText("Exact scope"), projectId); await waitFor(() => expect(requests).toHaveLength(3)); requests[2].resolve(response({ items: [item({ project_id: projectId, content: "current project" })], next_cursor: null })); await screen.findByText("current project"); requests[1].resolve(response({ items: [item({ content: "stale page" })], next_cursor: null })); await Promise.resolve(); expect(screen.queryByText("stale page")).not.toBeInTheDocument(); expect(screen.getByText("current project")).toBeInTheDocument();
  });

  it("renders hostile content inert and requires deliberate retry with the authoritative revision", async () => {
    const hostile = `<script>alert(1)</script> [go](javascript:x) \u202e Settings\n${"x".repeat(1200)}`; let patchCalls = 0;
    const revisions: number[] = []; const fetchMock = vi.fn(async (url: string, init?: RequestInit) => { if (url.includes("/projects?")) return response(projects); if (url.endsWith("/query")) return response({ items: [item({ content: hostile })], next_cursor: null }); if (url.endsWith("/detail")) return response(item({ content: hostile })); if ((init?.method) === "PATCH") { patchCalls += 1; revisions.push(body([url, init!]).revision as number); return patchCalls === 1 ? response({ detail: { error: "capture revision conflict", item: item({ content: "authoritative", revision: 2 }) } }, 409) : response(item({ content: "retried", revision: 3 })); } return response({}); }); renderInbox(fetchMock); const open = await screen.findByRole("button", { name: new RegExp("script") }); await userEvent.click(open); expect(document.querySelector("script")).toBeNull(); expect(screen.queryByRole("link", { name: "go" })).not.toBeInTheDocument();
    const edit = screen.getByLabelText("Edit plain text"); await userEvent.clear(edit); await userEvent.type(edit, "stale change"); await userEvent.click(screen.getByRole("button", { name: "Save edit" })); expect(await screen.findByText(/item changed; refreshed/i)).toBeInTheDocument(); expect(screen.getAllByText("authoritative").length).toBeGreaterThan(0); expect(patchCalls).toBe(1); await userEvent.click(screen.getByRole("button", { name: "Save edit" })); await waitFor(() => expect(patchCalls).toBe(2)); expect(revisions).toEqual([1, 2]);
  });

  it("uses the scoped resolver before showing a processed Source and never fetches it unscoped", async () => {
    const processed = item({ state: "processed", revision: 2, processed_at: "2026-09-19T09:00:00Z", resulting_source_id: sourceId }); const urls: string[] = [];
    const fetchMock = vi.fn(async (url: string) => { urls.push(url); if (url.includes("/projects?")) return response(projects); if (url.endsWith("/query")) return response({ items: [processed], next_cursor: null }); if (url.endsWith("/detail")) return response(processed); if (url.endsWith("/source")) return response(source); return response({}, 404); }); renderInbox(fetchMock); await userEvent.selectOptions(await screen.findByLabelText("State"), "processed"); await userEvent.click(await screen.findByRole("button", { name: /plain note/ })); await userEvent.click(screen.getByRole("button", { name: "Reopen scoped Source" })); expect(await screen.findByRole("heading", { name: "Authorized Source" })).toBeInTheDocument();
    const resolverCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith(`/capture-items/${captureId}/source`))!; expect(body(resolverCall)).toEqual({ scope: { unassigned: true } }); expect(urls.some(url => url.includes(`/sources/${sourceId}`))).toBe(false);
    for (const name of ["Save edit", "Reassign", "Discard", "Restore", "Convert to Source"]) expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
  });

  it("sends observed revision and exact scope for reassign, discard, restore, and conversion", async () => {
    let viewState: "pending" | "discarded" = "pending"; const actionCalls: Array<[string, RequestInit]> = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/projects?")) return response(projects);
      if (url.endsWith("/query")) { const requested = body([url, init!]).scope as Record<string, unknown>; return response({ items: [item({ state: viewState, project_id: requested.project_id ?? null })], next_cursor: null }); }
      if (url.endsWith("/detail")) { const requested = body([url, init!]).scope as Record<string, unknown>; return response(item({ state: viewState, project_id: requested.project_id ?? null })); }
      actionCalls.push([url, init!]);
      if (init?.method === "PATCH") return response(item({ content: "edited", revision: 2 }));
      if (url.endsWith("/reassign")) return response(item({ project_id: projectId, revision: 2 }));
      if (url.endsWith("/discard")) return response(item({ project_id: projectId, state: "discarded", revision: 2 }));
      if (url.endsWith("/restore")) return response(item({ project_id: projectId, state: "pending", revision: 2 }));
      if (url.endsWith("/convert-to-source")) return response({ capture: item({ project_id: projectId, state: "processed", revision: 2, processed_at: "2026-09-19T09:00:00Z", resulting_source_id: sourceId }), source });
      return response({});
    });
    renderInbox(fetchMock); await userEvent.click(await screen.findByRole("button", { name: /plain note/ })); await userEvent.clear(screen.getByLabelText("Edit plain text")); await userEvent.type(screen.getByLabelText("Edit plain text"), "edited"); await userEvent.click(screen.getByRole("button", { name: "Save edit" })); await waitFor(() => expect(actionCalls).toHaveLength(1)); expect(actionCalls[0][0]).toContain(`/capture-items/${captureId}`); expect(actionCalls[0][1].method).toBe("PATCH"); expect(body(actionCalls[0])).toEqual({ scope: { unassigned: true }, revision: 1, content: "edited" });
    await userEvent.selectOptions(screen.getByLabelText("Reassign to"), projectId); await userEvent.click(screen.getByRole("button", { name: "Reassign" })); await waitFor(() => expect(actionCalls).toHaveLength(2)); expect(body(actionCalls[1])).toEqual({ scope: { unassigned: true }, target_scope: { project_id: projectId }, revision: 2 }); expect(screen.queryByRole("heading", { name: "Capture detail" })).not.toBeInTheDocument();
    viewState = "pending"; await userEvent.selectOptions(screen.getByLabelText("Exact scope"), projectId); await userEvent.click(await screen.findByRole("button", { name: /plain note/ })); await userEvent.click(screen.getByRole("button", { name: "Discard" })); await waitFor(() => expect(actionCalls).toHaveLength(3)); expect(body(actionCalls[2])).toMatchObject({ scope: { project_id: projectId }, revision: 1 });
    viewState = "discarded"; await userEvent.selectOptions(screen.getByLabelText("State"), "discarded"); await userEvent.click(await screen.findByRole("button", { name: /plain note/ })); await userEvent.click(screen.getByRole("button", { name: "Restore" })); await waitFor(() => expect(actionCalls).toHaveLength(4)); expect(body(actionCalls[3])).toMatchObject({ scope: { project_id: projectId }, revision: 1 });
    viewState = "pending"; await userEvent.selectOptions(screen.getByLabelText("State"), "pending"); await userEvent.click(await screen.findByRole("button", { name: /plain note/ })); await userEvent.click(screen.getByRole("button", { name: "Convert to Source" })); await screen.findByRole("heading", { name: "Authorized Source" }); expect(body(actionCalls[4])).toMatchObject({ scope: { project_id: projectId }, revision: 1 });
  });

  it.each([
    ["invalid state", { state: "unknown" }],
    ["empty content", { content: "   " }],
    ["oversized content", { content: "x".repeat(8001) }],
    ["invalid scalar", { content: "bad\ud800" }],
    ["NUL content", { content: "bad\u0000content" }],
    ["carriage-return content", { content: "bad\rcontent" }],
    ["CRLF content", { content: "bad\r\ncontent" }],
    ["processed without provenance", { state: "processed", processed_at: null, resulting_source_id: null }],
    ["pending with provenance", { processed_at: "2026-09-19T09:00:00Z", resulting_source_id: sourceId }],
    ["discarded with provenance", { state: "discarded", processed_at: "2026-09-19T09:00:00Z", resulting_source_id: sourceId }],
    ["invalid identity fields", { id: "not-a-uuid", revision: 0, updated_at: "not-a-time" }],
  ])("rejects malformed authoritative conflict data: %s", async (_name, overrides) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: { error: "capture revision conflict", item: item(overrides) } }, 409)));
    await expect(editCapture(captureId, { unassigned: true }, 1, "change")).rejects.toBeInstanceOf(SafeApiError);
  });

  it("keeps visible Capture state unchanged for NUL, CR, and CRLF conflict projections", async () => {
    const malformed = ["bad\u0000content", "bad\rcontent", "bad\r\ncontent"]; let patch = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => { if (url.includes("/projects?")) return response(projects); if (url.endsWith("/query")) return response({ items: [item()], next_cursor: null }); if (url.endsWith("/detail")) return response(item()); if (init?.method === "PATCH") return response({ detail: { error: "capture revision conflict", item: item({ content: malformed[patch++]!, revision: 2 }) } }, 409); return response({}); });
    renderInbox(fetchMock); await userEvent.click(await screen.findByRole("button", { name: /plain note/ }));
    for (const [index, content] of malformed.entries()) { await userEvent.click(screen.getByRole("button", { name: "Save edit" })); await waitFor(() => expect(patch).toBe(index + 1)); expect(screen.getByText("The action could not be completed.")).toBeInTheDocument(); expect(screen.getAllByText("plain note").length).toBeGreaterThan(0); expect(screen.queryByText(content)).not.toBeInTheDocument(); expect(screen.getByText("Revision").nextElementSibling).toHaveTextContent("1"); }
    expect(patch).toBe(3);
  });

  it("uses no polling interval or browser persistence during Inbox operation", async () => {
    const interval = vi.spyOn(window, "setInterval"); renderInbox(); await act(async () => { await Promise.resolve(); await Promise.resolve(); }); expect(screen.getByText("plain note")).toBeInTheDocument(); expect(interval).not.toHaveBeenCalled(); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  });
});
