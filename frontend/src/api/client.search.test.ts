import { afterEach, describe, expect, it, vi } from "vitest";
import { searchMemories } from "./client";

const response = (body: unknown): Response => ({ ok: true, status: 200, json: vi.fn().mockResolvedValue(body) } as unknown as Response);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

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
