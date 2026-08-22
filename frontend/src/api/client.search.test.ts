import { afterEach, describe, expect, it, vi } from "vitest";
import { executeAgentRun, getAgentRun, planAgentRun, SafeApiError, searchMemories } from "./client";

const response = (body: unknown): Response => ({ ok: true, status: 200, json: vi.fn().mockResolvedValue(body) } as unknown as Response);

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function abortingFetch() {
  return vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
  }));
}

describe("legacy searchMemories", () => {
  it("preserves the lexical GET contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([])); vi.stubGlobal("fetch", fetchMock);
    await searchMemories("lexical", "needle", { status: "active" }, 7);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memories?query=needle&limit=7&offset=0&status=active");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "GET" });
  });

  it("preserves the semantic and hybrid POST contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response([])); vi.stubGlobal("fetch", fetchMock);
    await searchMemories("hybrid", "meaning", {}, 20);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memories/search");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1].body))).toEqual({ query: "meaning", mode: "hybrid", filters: {}, pagination: { limit: 20, offset: 0 } });
  });
});

describe("Agent request timeouts", () => {
  it("keeps ordinary reads at five seconds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", abortingFetch());
    const request = getAgentRun("11111111-1111-4111-8111-111111111111").catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(4_999);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(await request).toBeInstanceOf(SafeApiError);
  });

  it("preserves the bounded 35-second planning timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", abortingFetch());
    const request = planAgentRun("11111111-1111-4111-8111-111111111111", 1).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(5_000);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(await request).toBeInstanceOf(SafeApiError);
  });

  it("allows the bounded backend execution window before interruption", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", abortingFetch());
    const request = executeAgentRun("11111111-1111-4111-8111-111111111111", 2).catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(35_000);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(629_999);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(await request).toBeInstanceOf(SafeApiError);
  });
});
