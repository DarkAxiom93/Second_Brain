import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const projectId = "11111111-1111-4111-8111-111111111111";
const token = "opaque-secret-reopen-token";
const scope = { project_id: projectId, unassigned: false } as const;
const item = (family: "local_source" | "github" | "google_calendar", overrides = {}) => ({
  contract_version: "context-hub-v1", family,
  kind: family === "local_source" ? "source_chunk" : family === "github" ? "issue" : "calendar_event",
  scope, trust: family === "local_source" ? "local_audited" : "quarantined_external",
  state: family === "local_source" ? "extracted" : "current", title: `${family} title`, text: `${family} text`, reopen_id: token, ...overrides,
});
const projects = [{ id: projectId, name: "Alpha", description: null, created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" }];
const facets = { contract_version: "context-hub-v1", observed_at: "2026-09-08T10:00:00Z", families: [{ value: "local_source", count: 1 }], kinds: [{ value: "source_chunk", count: 1 }], trust: [{ value: "local_audited", count: 1 }], states: [{ value: "extracted", count: 1 }] };
function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response; }
function emptyPage(cursor: string | null = null) { return { contract_version: "context-hub-v1", groups: ["local_source", "github", "google_calendar"].map((family) => ({ family, items: [], exhausted: cursor === null })), next_cursor: cursor }; }
function renderHub() { return render(<MemoryRouter initialEntries={["/context-hub"]}><App /></MemoryRouter>); }
function bodyOf(call: unknown[]) { return JSON.parse((call[1] as RequestInit).body as string) as Record<string, unknown>; }

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); sessionStorage.clear(); });

describe("Context Hub", () => {
  it("provides the route and navigation but performs no Hub read before exact scope submission", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(projects)); vi.stubGlobal("fetch", fetchMock); renderHub();
    expect(screen.getByRole("link", { name: "Context Hub" })).toHaveClass("active");
    expect(screen.getByRole("heading", { name: "Context Hub" })).toBeInTheDocument();
    await screen.findByRole("option", { name: "Alpha" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    expect(within(screen.getByRole("main")).getByRole("status")).toHaveTextContent("Select one Project or explicit unassigned scope");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends deterministic Project and explicit-unassigned requests only on Search", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(emptyPage())).mockResolvedValueOnce(response(facets)).mockResolvedValueOnce(response(emptyPage())).mockResolvedValueOnce(response(facets));
    vi.stubGlobal("fetch", fetchMock); renderHub(); const select = await screen.findByLabelText("Exact scope");
    await userEvent.selectOptions(select, projectId); await userEvent.type(screen.getByLabelText(/Text query/), " bounded "); await userEvent.click(screen.getByLabelText("Issue")); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    await screen.findByText("No context matched this request.");
    const hubCalls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/context-hub/")); expect(hubCalls).toHaveLength(2);
    expect(bodyOf(hubCalls[0])).toEqual({ scope, families: ["local_source", "github", "google_calendar"], kinds: ["issue"], trust: [], states: [], query: "bounded", page_size: 20 });
    await userEvent.selectOptions(select, "unassigned"); expect(screen.queryByRole("heading", { name: "Results" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(bodyOf(fetchMock.mock.calls[3])).toMatchObject({ scope: { project_id: null, unassigned: true } });
  });

  it("renders fixed family order and visible kind, trust, state, scope, provenance, and exact facets", async () => {
    const page = { contract_version: "context-hub-v1", groups: [
      { family: "google_calendar", items: [item("google_calendar")], exhausted: true },
      { family: "github", items: [item("github")], exhausted: true },
      { family: "local_source", items: [item("local_source")], exhausted: true },
    ], next_cursor: null };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(page)).mockResolvedValueOnce(response(facets)); vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    const results = await screen.findByRole("heading", { name: "Results" }); const headings = within(results.parentElement!).getAllByRole("heading", { level: 3 }).map((node) => node.textContent);
    expect(headings).toEqual(["Local source", "GitHub", "Google Calendar"]);
    expect(screen.getAllByText("Local audited").length).toBeGreaterThan(0); expect(screen.getAllByText("Quarantined external").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(0); expect(screen.getByText(/Request-time observation/)).toBeInTheDocument();
    expect(screen.getAllByText("Exact audited Source → Document → Chunk.").length).toBeGreaterThan(0);
  });

  it("paginates with the canonical applied snapshot and invalidates the cursor when controls change", async () => {
    const first = emptyPage("opaque-cursor"); const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(first)).mockResolvedValueOnce(response(facets)).mockResolvedValueOnce(response(emptyPage()));
    vi.stubGlobal("fetch", fetchMock); renderHub(); await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    await userEvent.click(await screen.findByRole("button", { name: "Load next page" })); await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(bodyOf(fetchMock.mock.calls[3])).toMatchObject({ scope, cursor: "opaque-cursor", page_size: 20 });
    await userEvent.type(screen.getByLabelText(/Text query/), "changed"); expect(screen.queryByRole("button", { name: "Load next page" })).not.toBeInTheDocument(); expect(screen.queryByRole("heading", { name: "Results" })).not.toBeInTheDocument();
  });

  it("keeps hostile content inert and reopens detail in-page without exposing or persisting the token", async () => {
    const hostile = `<script>window.pwned=1</script> [go](javascript:alert(1)) https://evil.example \u202E Settings`;
    const hostileItem = item("github", { title: hostile, text: hostile }); const page = { contract_version: "context-hub-v1", groups: [{ family: "local_source", items: [], exhausted: true }, { family: "github", items: [hostileItem], exhausted: true }, { family: "google_calendar", items: [], exhausted: true }], next_cursor: null };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(page)).mockResolvedValueOnce(response(facets)).mockResolvedValueOnce(response(hostileItem)); vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    const open = await screen.findByRole("button", { name: "Open exact Issue detail" }); expect(document.querySelector("script")).toBeNull(); expect(screen.queryByRole("link", { name: /evil|go/i })).not.toBeInTheDocument(); expect(document.body).not.toHaveTextContent(token);
    open.focus(); await userEvent.click(open); const close = await screen.findByRole("button", { name: "Close detail and return to result" }); await waitFor(() => expect(close).toHaveFocus());
    expect(window.location.pathname).toBe("/"); expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0); expect(document.body).not.toHaveTextContent(token);
    await userEvent.click(close); expect(open).toHaveFocus(); expect(bodyOf(fetchMock.mock.calls[3])).toEqual({ scope, family: "github", reopen_id: token });
  });

  it("contains the complete hostile rendering corpus without execution navigation or label spoofing", async () => {
    const corpus = ["<img src=x onerror=alert(1)>", "<svg onload=alert(1)>", "[tool](javascript:alert(1))", "![track](data:text/html,boom)", "\u202ESettings\u2066trusted\u2069", "C0:\u0001 C1:\u0085", "confusable cÐ¾ntext-hub", "x".repeat(4000)];
    const hostileItem = item("google_calendar", { title: corpus[0], text: corpus.join(" | "), trust: "local_audited", state: "deleted" });
    const page = { contract_version: "context-hub-v1", groups: [{ family: "local_source", items: [], exhausted: true }, { family: "github", items: [], exhausted: true }, { family: "google_calendar", items: [hostileItem], exhausted: true }], next_cursor: null };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(page)).mockResolvedValueOnce(response(facets)); vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    await screen.findByRole("button", { name: "Open exact Calendar event detail" });
    expect(document.querySelector("script, img, svg, style, iframe")).toBeNull();
    expect(screen.getAllByRole("link").every((link) => !/javascript:|data:/i.test(link.getAttribute("href") ?? ""))).toBe(true);
    expect(window.location.pathname).toBe("/"); expect((globalThis as { cp113Executed?: boolean }).cp113Executed).toBeUndefined();
    expect(screen.getByText("Quarantined external")).toBeInTheDocument(); expect(screen.getByText("Current")).toBeInTheDocument();
    for (const forbidden of ["Refresh", "Import", "Schedule", "Write"]) expect(screen.queryByRole("button", { name: new RegExp(forbidden, "i") })).not.toBeInTheDocument();
  });

  it("keeps excluded privacy and capability canaries out of the DOM", async () => {
    const canaries = ["cp113-credential-canary", "cp113-provider-canary", "cp113-private-canary", "cp113-config-canary"];
    const safeItem = item("github", { title: "safe", text: "safe" });
    const page = { contract_version: "context-hub-v1", groups: [{ family: "local_source", items: [], exhausted: true }, { family: "github", items: [safeItem], exhausted: true }, { family: "google_calendar", items: [], exhausted: true }], next_cursor: "opaque-cursor" };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(page)).mockResolvedValueOnce(response(facets)).mockResolvedValueOnce(response({}, 404)); vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    await userEvent.click(await screen.findByRole("button", { name: "Open exact Issue detail" })); await screen.findByRole("alert");
    const serialized = document.documentElement.textContent + document.documentElement.innerHTML;
    for (const canary of canaries) expect(serialized).not.toContain(canary);
    expect(serialized).not.toContain(token); expect(serialized).not.toContain("opaque-cursor");
  });

  it("announces exact facet-limit, loading, empty, and safe error states without adding authority controls", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(projects)).mockResolvedValueOnce(response(emptyPage())).mockResolvedValueOnce(response({}, 422)); vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId); await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    expect(await screen.findByText(/Counts unavailable for this request/)).toBeInTheDocument(); expect(screen.getByText("No context matched this request.")).toHaveAttribute("role", "status");
    for (const forbidden of ["Refresh", "Import", "Schedule", "Write"]) expect(screen.queryByRole("button", { name: new RegExp(forbidden, "i") })).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Families" })).toBeInTheDocument(); expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("completes the CP114 hostile keyboard detail and pagination journey without capability leakage", async () => {
    const hostile = `<script>cp114=1</script> [go](javascript:alert(1)) \u202E Settings ${"x".repeat(1200)}`;
    const page = { contract_version: "context-hub-v1", groups: [
      { family: "local_source", items: [item("local_source", { title: hostile, text: hostile })], exhausted: false },
      { family: "github", items: [item("github", { title: hostile, text: hostile, reopen_id: `${token}-github` })], exhausted: false },
      { family: "google_calendar", items: [item("google_calendar", { title: hostile, text: hostile, reopen_id: `${token}-calendar` })], exhausted: false },
    ], next_cursor: "cp114-opaque-cursor" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(projects))
      .mockResolvedValueOnce(response(page))
      .mockResolvedValueOnce(response(facets))
      .mockResolvedValueOnce(response(page.groups[0].items[0]))
      .mockResolvedValueOnce(response(emptyPage()));
    vi.stubGlobal("fetch", fetchMock); renderHub();
    await userEvent.selectOptions(await screen.findByLabelText("Exact scope"), projectId);
    await userEvent.click(screen.getByRole("button", { name: "Search context" }));
    expect((await screen.findAllByText(hostile)).length).toBeGreaterThan(0);
    expect(document.querySelector("script, img, svg, iframe")).toBeNull();
    expect(screen.getByRole("heading", { name: "Results" }).parentElement).toHaveAttribute("aria-busy", "false");
    const open = screen.getByRole("button", { name: "Open exact Source chunk detail" });
    open.focus(); await userEvent.keyboard("{Enter}");
    const close = await screen.findByRole("button", { name: "Close detail and return to result" });
    await userEvent.click(close); expect(open).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Load next page" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
    expect(bodyOf(fetchMock.mock.calls[4])).toMatchObject({ scope, cursor: "cp114-opaque-cursor" });
    expect(document.body.innerHTML).not.toContain(token);
    expect(document.body.innerHTML).not.toContain("cp114-opaque-cursor");
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
    expect(screen.queryByRole("link", { name: /javascript|go/i })).not.toBeInTheDocument();
  });
});
