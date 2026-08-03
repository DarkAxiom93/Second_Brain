import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Memories, MemoryDetail } from "./Memories";

const ID = "11111111-1111-4111-8111-111111111111";
const OTHER = "22222222-2222-4222-8222-222222222222";
const memory = { id: ID, project_id: null, content: "Private evidence body", source: null, title: "A fact", summary: "Safe summary", memory_type: "semantic", importance: .7, confidence: .8, status: "active", event_time: null, expires_at: null, supersedes_id: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const response = (body: unknown, status = 200): Response => ({ ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response);
function list() { return render(<MemoryRouter><Memories /></MemoryRouter>); }
function detail(path = `/memories/${ID}`) { return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/memories/:memoryId" element={<MemoryDetail />}/><Route path="/memories" element={<Memories />}/></Routes></MemoryRouter>); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("Memories browser", () => {
  it("renders a real page without N+1 detail requests and keeps evidence off cards", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([memory])); vi.stubGlobal("fetch", fetchMock); list();
    expect(await screen.findByRole("link", { name: "A fact" })).toHaveAttribute("href", `/memories/${ID}`);
    expect(screen.queryByText("Private evidence body")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("applies persisted filters and paginates", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(Array(20).fill(null).map((_, i) => ({ ...memory, id: `${String(i + 1).padStart(8, "0")}-1111-4111-8111-111111111111` })))); vi.stubGlobal("fetch", fetchMock); list(); await screen.findAllByRole("link", { name: "A fact" });
    await userEvent.selectOptions(screen.getByLabelText("Status"), "expired"); await userEvent.type(screen.getByLabelText(/Minimum confidence/), "0.6"); await userEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith("/api/memories?status=expired&confidence_min=0.6&limit=20&offset=0", expect.anything()));
    await userEvent.click(screen.getByRole("button", { name: "Next" })); await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith(expect.stringContaining("offset=20"), expect.anything()));
  });
  it("shows failure and supports manual Retry", async () => { const fetchMock = vi.fn().mockRejectedValueOnce(new Error()).mockResolvedValueOnce(response([])); vi.stubGlobal("fetch", fetchMock); list(); await userEvent.click(await screen.findByRole("button", { name: "Retry" })); expect(await screen.findByText(/No Memories match/)).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(2); });
});

describe("Memory detail", () => {
  it("rejects malformed UUID locally", () => { const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); detail("/memories/not-a-uuid"); expect(screen.getByRole("heading", { name: "Invalid Memory address" })).toBeInTheDocument(); expect(fetchMock).not.toHaveBeenCalled(); });
  it("renders detail provenance and advisories only after detail retrieval", async () => {
    const fetchMock = vi.fn((url: string) => { if (url.endsWith("/sources?limit=100&offset=0")) return Promise.resolve(response([{ link_id: OTHER, memory_id: ID, source_id: OTHER, source_location: "lines 1-2", linked_at: "2026-01-01T00:00:00Z", source_type: "note", name: "Notebook", reference: null, checksum: null, source_created_at: "2026-01-01T00:00:00Z", source_updated_at: "2026-01-01T00:00:00Z" }])); if (url.includes("similarities")) return Promise.resolve(response({ target_memory_id: ID, candidates: [] })); if (url.includes("contradictions")) return Promise.resolve(response({ target_memory_id: ID, candidates: [] })); return Promise.resolve(response(memory)); }); vi.stubGlobal("fetch", fetchMock); detail();
    expect(await screen.findByText("Private evidence body")).toBeInTheDocument(); expect(screen.getByRole("link", { name: "Notebook" })).toBeInTheDocument(); expect(await screen.findAllByText(/Read-only advisory/)).toHaveLength(2); expect(fetchMock).toHaveBeenCalledTimes(4);
  });
  it("submits exact quality values and refetches without optimistic mutation", async () => {
    // The mock retains the Fetch signature so its captured init can be asserted below.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    let reads = 0; const fetchMock = vi.fn((url: string, init: RequestInit) => { if (url.includes("/sources")) return Promise.resolve(response([])); if (url.includes("similarities") || url.includes("contradictions")) return Promise.resolve(response({ target_memory_id: ID, candidates: [] })); if (url.endsWith("/quality")) return Promise.resolve(response({ refinement_status: "updated", memory: { ...memory, confidence: .9, importance: .6 } })); reads++; return Promise.resolve(response(reads > 1 ? { ...memory, confidence: .9, importance: .6 } : memory)); }); vi.stubGlobal("fetch", fetchMock); detail(); await screen.findByText("Private evidence body"); await userEvent.clear(screen.getByLabelText("Confidence")); await userEvent.type(screen.getByLabelText("Confidence"), "0.9"); await userEvent.clear(screen.getByLabelText("Importance")); await userEvent.type(screen.getByLabelText("Importance"), "0.6"); await userEvent.click(screen.getByRole("button", { name: "Save quality" })); await screen.findByText(/Quality completed/); const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/quality")); expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ confidence: .9, importance: .6 }); expect(reads).toBe(2);
  });
  it("validates supersession self-reference without submitting", async () => { const fetchMock = vi.fn((url: string) => url.includes("/sources") ? Promise.resolve(response([])) : url.includes("similarities") || url.includes("contradictions") ? Promise.resolve(response({ target_memory_id: ID, candidates: [] })) : Promise.resolve(response(memory))); vi.stubGlobal("fetch", fetchMock); detail(); await screen.findByText("Private evidence body"); await userEvent.type(screen.getByLabelText("Replacement Memory UUID"), ID); await userEvent.click(screen.getByRole("button", { name: "Supersede Memory" })); expect(await screen.findByText(/cannot supersede itself/)).toBeInTheDocument(); expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/supersede"))).toBe(false); });
});
