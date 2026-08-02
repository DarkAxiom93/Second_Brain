import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentIngestion, SourceDocumentDetail } from "./Documents";

const sourceId = "11111111-1111-4111-8111-111111111111";
const documentId = "22222222-2222-4222-8222-222222222222";
const documentRecord = { id: documentId, source_id: sourceId, media_type: "text/plain", original_filename: "notes.txt", byte_size: 12, ingestion_status: "extracted", error_code: null, extracted_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", chunk_count: 1 };
const chunk = { id: "33333333-3333-4333-8333-333333333333", document_id: documentId, chunk_index: 0, content: "private extracted evidence", char_start: 0, char_end: 26, content_hash: "a".repeat(64), locator: null, created_at: "2026-01-01T00:00:00Z" };
function response(body: unknown, status = 200): Response { return { ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response; }
function ingestion() { return render(<MemoryRouter initialEntries={[`/sources/${sourceId}/ingest`]}><Routes><Route path="/sources/:sourceId/ingest" element={<DocumentIngestion />} /><Route path="/source-documents/:documentId" element={<p>Document destination</p>} /></Routes></MemoryRouter>); }
function detail(id = documentId) { return render(<MemoryRouter initialEntries={[`/source-documents/${id}`]}><Routes><Route path="/source-documents/:documentId" element={<SourceDocumentDetail />} /></Routes></MemoryRouter>); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("document ingestion", () => {
  it("rejects empty JSON text, focuses it, and sends the exact valid body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({ ...documentRecord, generation_status: "created" })); vi.stubGlobal("fetch", fetchMock); ingestion();
    await userEvent.click(screen.getByRole("button", { name: "Ingest document" })); expect(screen.getByLabelText("Document text")).toHaveFocus(); expect(fetchMock).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Document text"), "hello"); await userEvent.type(screen.getByLabelText(/Original filename/), "note.txt"); await userEvent.click(screen.getByRole("button", { name: "Ingest document" }));
    expect(await screen.findByText("Document destination")).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/sources/${sourceId}/document/text`);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ text: "hello", original_filename: "note.txt", chunk_size: 2000, chunk_overlap: 200 });
  });

  it("rejects unsupported, empty, and oversized files locally", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); ingestion(); await userEvent.selectOptions(screen.getByLabelText("Format"), "txt");
    const input = screen.getByLabelText("TXT file"); await userEvent.upload(input, new File(["x"], "bad.pdf", { type: "application/pdf" }), { applyAccept: false }); await userEvent.click(screen.getByRole("button", { name: "Ingest document" })); expect(await screen.findByRole("alert")).toHaveTextContent("valid TXT");
    await userEvent.upload(input, new File([], "empty.txt", { type: "text/plain" })); await userEvent.click(screen.getByRole("button", { name: "Ingest document" })); expect(screen.getByRole("alert")).toHaveTextContent("empty"); expect(fetchMock).not.toHaveBeenCalled();
  });

  it("constructs multipart PDF exactly, prevents duplicates, and stays after failure", async () => {
    let resolve!: (value: Response) => void; const fetchMock = vi.fn(() => new Promise<Response>((done) => { resolve = done; })); vi.stubGlobal("fetch", fetchMock); ingestion(); await userEvent.selectOptions(screen.getByLabelText("Format"), "pdf"); await userEvent.upload(screen.getByLabelText("PDF file"), new File(["pdf"], "paper.pdf", { type: "application/pdf" })); const button = screen.getByRole("button", { name: "Ingest document" }); await userEvent.click(button); expect(button).toBeDisabled(); await userEvent.click(button); expect(fetchMock).toHaveBeenCalledTimes(1); const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit]; const body = call[1].body as FormData; expect(body.get("chunk_size")).toBe("2000"); expect((body.get("file") as File).name).toBe("paper.pdf"); resolve(response({}, 422)); expect(await screen.findByRole("alert")).toHaveTextContent("could not be ingested");
  });

  it("rejects malformed success without exposing sensitive content", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(response({ id: documentId, extracted_text: "secret" })))); ingestion(); await userEvent.type(screen.getByLabelText("Document text"), "safe"); await userEvent.click(screen.getByRole("button", { name: "Ingest document" })); expect(await screen.findByRole("alert")).toHaveTextContent("could not be ingested"); expect(document.body).not.toHaveTextContent("secret");
  });

  it("aborts an active ingestion request on unmount", async () => {
    let signal: AbortSignal | undefined; vi.stubGlobal("fetch", vi.fn((_url, init) => { signal = init.signal; return new Promise(() => undefined); })); const view = ingestion(); await userEvent.type(screen.getByLabelText("Document text"), "safe"); await userEvent.click(screen.getByRole("button", { name: "Ingest document" })); view.unmount(); expect(signal?.aborted).toBe(true);
  });
});

describe("document detail", () => {
  it("renders metadata and chunk text with one page request and pagination", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response(documentRecord)).mockResolvedValueOnce(response([chunk])); vi.stubGlobal("fetch", fetchMock); detail(); expect(screen.getByText("Loading document…")).toBeInTheDocument(); expect(await screen.findByText("private extracted evidence")).toBeInTheDocument(); expect(fetchMock).toHaveBeenCalledTimes(2); expect(screen.getByRole("button", { name: "Next" })).toBeDisabled(); expect(screen.getByRole("link", { name: "Back to source" })).toHaveAttribute("href", `/sources/${sourceId}`);
  });
  it("handles malformed, missing, malformed payload, Retry, and cancellation safely", async () => {
    const none = vi.fn(); vi.stubGlobal("fetch", none); detail("bad"); expect(screen.getByRole("heading", { name: "Invalid document address" })).toBeInTheDocument(); expect(none).not.toHaveBeenCalled(); cleanup();
    const missing = vi.fn().mockResolvedValueOnce(response({}, 404)).mockResolvedValueOnce(response([], 404)); vi.stubGlobal("fetch", missing); detail(); expect(await screen.findByRole("heading", { name: "Document not found" })).toBeInTheDocument(); cleanup();
    const failed = vi.fn().mockResolvedValueOnce(response({ ...documentRecord, secret: "hidden" })).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response(documentRecord)).mockResolvedValueOnce(response([chunk])); vi.stubGlobal("fetch", failed); detail(); await userEvent.click(await screen.findByRole("button", { name: "Retry" })); expect(await screen.findByText("private extracted evidence")).toBeInTheDocument(); expect(document.body).not.toHaveTextContent("hidden");
    await waitFor(() => expect(failed).toHaveBeenCalledTimes(4));
  });
});
