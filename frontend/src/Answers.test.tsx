import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Answers } from "./Answers";

const projectId = "11111111-1111-4111-8111-111111111111";
const memoryId1 = "22222222-2222-4222-8222-222222222222";
const memoryId2 = "33333333-3333-4333-8333-333333333333";

function memory(id: string, content: string) {
  return { id, project_id: projectId, content, source: null, title: null, summary: null, memory_type: "semantic", importance: .5, confidence: .9, status: "active", event_time: null, expires_at: null, supersedes_id: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
}
function answer(citations: unknown[] = []) { return { answer_status: citations.length ? "answered" : "insufficient_evidence", answer: citations.length ? "Returned answer" : "I do not have enough evidence to answer that question.", search_mode: "lexical", citations }; }
function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response; }
function renderAnswers() { return render(<MemoryRouter><Answers /></MemoryRouter>); }
async function fill(question = "  What is supported?  ") { await userEvent.type(screen.getByLabelText("Project UUID (optional; blank searches unassigned Memories)"), projectId); await userEvent.clear(screen.getByLabelText("Question")); await userEvent.type(screen.getByLabelText("Question"), question); await userEvent.selectOptions(screen.getByLabelText("Retrieval mode"), "lexical"); await userEvent.clear(screen.getByLabelText("Evidence limit")); await userEvent.type(screen.getByLabelText("Evidence limit"), "2"); }

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("evidence-backed answers", () => {
  it("makes no request before explicit submission and validates the first invalid control", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); renderAnswers();
    await userEvent.type(screen.getByLabelText("Question"), "draft");
    expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.clear(screen.getByLabelText("Question")); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a question"); expect(screen.getByLabelText("Question")).toHaveFocus();
  });

  it("submits the exact established request and renders evidence in returned order without detail requests", async () => {
    const citations = [
      { label: "M2", rank: 2, memory: memory(memoryId2, "second evidence"), lexical_score: .4, semantic_score: null },
      { label: "M1", rank: 1, memory: memory(memoryId1, "first evidence"), lexical_score: .7, semantic_score: null },
    ];
    const fetchMock = vi.fn().mockResolvedValue(response(answer(citations))); vi.stubGlobal("fetch", fetchMock); renderAnswers(); await fill();
    await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText("Returned answer")).toBeInTheDocument();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ query: "What is supported?", project_id: projectId, search_mode: "lexical", limit: 2 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("listitem").map(item => item.textContent)).toEqual([expect.stringContaining("second evidence"), expect.stringContaining("first evidence")]);
    expect(screen.getByRole("link", { name: `Memory ${memoryId1}` })).toHaveAttribute("href", `/memories/${memoryId1}`);
    expect(document.body).not.toHaveTextContent("citation 1");
  });

  it("renders the valid no-evidence state without inventing support", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(answer()))); renderAnswers(); await userEvent.type(screen.getByLabelText("Question"), "Unknown?"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText("No supporting evidence was returned.")).toBeInTheDocument(); expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });

  it("retries only the last validated request, not mutable draft values", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({ detail: "database unavailable" }, 503)).mockResolvedValueOnce(response(answer())); vi.stubGlobal("fetch", fetchMock); renderAnswers(); await userEvent.type(screen.getByLabelText("Question"), "Original"); await userEvent.click(screen.getByRole("button", { name: "Submit question" }));
    expect(await screen.findByText("The local answer database is unavailable.")).toBeInTheDocument(); await userEvent.clear(screen.getByLabelText("Question")); await userEvent.type(screen.getByLabelText("Question"), "Unsent edit"); await userEvent.click(screen.getByRole("button", { name: "Retry last submitted question" }));
    await screen.findByText("No supporting evidence was returned."); expect(JSON.parse(fetchMock.mock.calls[1][1].body).query).toBe("Original");
  });

  it("aborts an obsolete explicit request, prevents duplicates, and keeps the latest response authoritative", async () => {
    let resolveFirst!: (value: Response) => void; const first = new Promise<Response>(resolve => { resolveFirst = resolve; });
    const fetchMock = vi.fn().mockReturnValueOnce(first).mockResolvedValueOnce(response(answer([{ label: "M1", rank: 1, memory: memory(memoryId1, "latest evidence"), lexical_score: 1, semantic_score: null }]))); vi.stubGlobal("fetch", fetchMock); renderAnswers(); await userEvent.type(screen.getByLabelText("Question"), "First"); const form = screen.getByRole("button", { name: "Submit question" }).closest("form")!; fireEvent.submit(form); fireEvent.submit(form); expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.clear(screen.getByLabelText("Question")); await userEvent.type(screen.getByLabelText("Question"), "Second"); fireEvent.submit(form); expect(fetchMock).toHaveBeenCalledTimes(2); expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true);
    expect(await screen.findByText("latest evidence")).toBeInTheDocument(); resolveFirst(response(answer([{ label: "M1", rank: 1, memory: memory(memoryId2, "obsolete evidence"), lexical_score: 1, semantic_score: null }]))); await waitFor(() => expect(document.body).not.toHaveTextContent("obsolete evidence"));
  });

  it("rejects malformed success and redacts unrecognized provider details", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response({ ...answer(), prompt: "hidden" })).mockResolvedValueOnce(response({ detail: "stack trace secret://credential" }, 502)); vi.stubGlobal("fetch", fetchMock); renderAnswers(); await userEvent.type(screen.getByLabelText("Question"), "Question"); await userEvent.click(screen.getByRole("button", { name: "Submit question" })); expect(await screen.findByText("The answer could not be completed safely.")).toBeInTheDocument(); expect(document.body).not.toHaveTextContent("hidden"); await userEvent.click(screen.getByRole("button", { name: "Retry last submitted question" })); await screen.findByText("The answer could not be completed safely."); expect(document.body).not.toHaveTextContent("secret"); expect(document.body).not.toHaveTextContent("stack trace");
  });
});
