import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SourceDetail, Sources } from "./Sources";

const id = "11111111-1111-4111-8111-111111111111";
const source = { id, source_type: "note", name: "Research notes", reference: "page 2", checksum: "abc", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" };
const memory = { link_id: "22222222-2222-4222-8222-222222222222", source_id: id, memory_id: "33333333-3333-4333-8333-333333333333", source_location: "paragraph 1", linked_at: "2026-01-03T00:00:00Z", project_id: null, content: "safe", legacy_source: null, title: "Linked fact", summary: null, memory_type: "fact", importance: 0.5, confidence: 0.5, status: "active", event_time: null, expires_at: null, supersedes_id: null, memory_created_at: "2026-01-03T00:00:00Z", memory_updated_at: "2026-01-03T00:00:00Z" };
function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response; }
function renderList() { return render(<MemoryRouter><Routes><Route path="/" element={<Sources />} /><Route path="/sources/:sourceId" element={<p>Created source page</p>} /></Routes></MemoryRouter>); }
function renderDetail(value = id) { return render(<MemoryRouter initialEntries={[`/sources/${value}`]}><Routes><Route path="/sources/:sourceId" element={<SourceDetail />} /></Routes></MemoryRouter>); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("sources list and creation", () => {
  it("shows loading, one list request, safe fields, and accessible pagination", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([source])); vi.stubGlobal("fetch", fetchMock); renderList();
    expect(screen.getByText("Loading sources…")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: source.name })).toHaveAttribute("href", `/sources/${id}`);
    expect(fetchMock).toHaveBeenCalledTimes(1); expect(fetchMock.mock.calls[0][0]).toBe("/api/sources?limit=20&offset=0");
    expect(screen.getByRole("navigation", { name: "Source pages" })).toBeInTheDocument();
  });

  it("handles empty, failure, and manual Retry without polling", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({}, 503)).mockResolvedValueOnce(response([])); vi.stubGlobal("fetch", fetchMock); renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No sources found.")).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 30)); expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("uses correct next-page parameters", async () => {
    const page = Array.from({ length: 20 }, (_, index) => ({ ...source, id: `${index.toString(16).padStart(8, "0")}-1111-4111-8111-111111111111`, name: `Source ${index}` }));
    const fetchMock = vi.fn().mockResolvedValueOnce(response(page)).mockResolvedValueOnce(response([])); vi.stubGlobal("fetch", fetchMock); renderList();
    await userEvent.click(await screen.findByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock.mock.calls[1][0]).toBe("/api/sources?limit=20&offset=20"));
  });

  it("focuses the first invalid field and sends the exact trimmed creation body", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response([])).mockResolvedValueOnce(response(source)); vi.stubGlobal("fetch", fetchMock); renderList();
    await userEvent.click(screen.getByRole("button", { name: "Create source" })); expect(screen.getByLabelText("Source type")).toHaveFocus();
    await userEvent.type(screen.getByLabelText("Source type"), " note "); await userEvent.type(screen.getByLabelText("Name"), " Research notes "); await userEvent.type(screen.getByLabelText(/Reference/), " page 2 ");
    await userEvent.click(screen.getByRole("button", { name: "Create source" }));
    expect(await screen.findByText("Created source page")).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ source_type: "note", name: "Research notes", reference: "page 2", checksum: null });
  });

  it("prevents duplicate submission and keeps values after failure", async () => {
    let resolveCreate!: (value: Response) => void;
    const fetchMock = vi.fn().mockResolvedValueOnce(response([])).mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveCreate = resolve; })); vi.stubGlobal("fetch", fetchMock); renderList();
    await userEvent.type(screen.getByLabelText("Source type"), "note"); await userEvent.type(screen.getByLabelText("Name"), "Keep me");
    const submit = screen.getByRole("button", { name: "Create source" }); await userEvent.click(submit); expect(submit).toBeDisabled(); expect(fetchMock).toHaveBeenCalledTimes(2);
    resolveCreate(response({}, 503)); expect(await screen.findByRole("alert")).toHaveTextContent("could not be created"); expect(screen.getByLabelText("Name")).toHaveValue("Keep me");
  });

  it("cancels list and creation requests on unmount", async () => {
    let signal: AbortSignal | undefined; vi.stubGlobal("fetch", vi.fn((_url, init) => { signal = init?.signal; return new Promise(() => undefined); }));
    const view = renderList(); expect(signal?.aborted).toBe(false); view.unmount(); expect(signal?.aborted).toBe(true);
  });
});

describe("source detail", () => {
  it("shows all fields and existing relationship summary", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(source)).mockResolvedValueOnce(response([memory])).mockResolvedValueOnce(response([])); vi.stubGlobal("fetch", fetchMock); renderDetail();
    expect(screen.getByText("Loading source…")).toBeInTheDocument(); expect(await screen.findByRole("heading", { name: source.name })).toBeInTheDocument();
    for (const value of [id, source.source_type, source.reference, source.checksum, memory.title]) expect(screen.getByText(value)).toBeInTheDocument();
    expect(screen.getByText(/paragraph 1/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3); expect(screen.getByRole("link", { name: "Ingest document" })).toHaveAttribute("href", `/sources/${id}/ingest`); expect(screen.getByText("No documents ingested.")).toBeInTheDocument();
  });

  it("sends no request for a malformed UUID", () => { const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); renderDetail("bad"); expect(screen.getByRole("heading", { name: "Invalid source address" })).toBeInTheDocument(); expect(fetchMock).not.toHaveBeenCalled(); });

  it("distinguishes missing and rejects malformed payloads safely", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({ detail: "source not found" }, 404)).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response([])); vi.stubGlobal("fetch", fetchMock); renderDetail(); expect(await screen.findByRole("heading", { name: "Source not found" })).toBeInTheDocument();
    cleanup(); fetchMock.mockReset().mockResolvedValueOnce(response({ ...source, internal: "secret" })).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response([])); renderDetail(); expect(await screen.findByRole("heading", { name: "Source unavailable" })).toBeInTheDocument(); expect(document.body).not.toHaveTextContent("secret");
  });

  it("cancels all detail requests on unmount", () => { const signals: AbortSignal[] = []; vi.stubGlobal("fetch", vi.fn((_url, init) => { signals.push(init.signal); return new Promise(() => undefined); })); const view = renderDetail(); view.unmount(); expect(signals).toHaveLength(3); expect(signals.every((signal) => signal.aborted)).toBe(true); });
});
