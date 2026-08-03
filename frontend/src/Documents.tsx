import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  generateMemoryProposals, getSourceDocument, ingestSourceFile, ingestSourceText, isSourceId,
  listSourceChunks, SourceDocumentNotFoundError, type SourceChunkRead,
  type SourceDocumentRead,
} from "./api/client";

const MAX_UPLOAD_BYTES = 20_000_000;
const MAX_TEXT_BYTES = 5_000_000;
const CHUNK_PAGE_SIZE = 20;
type Format = "json" | "txt" | "pdf";

function timestamp(value: string | null): string {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not available";
}

export function DocumentIngestion() {
  const { sourceId = "" } = useParams();
  const [format, setFormat] = useState<Format>("json");
  const [text, setText] = useState("");
  const [filename, setFilename] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const formatRef = useRef<HTMLSelectElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const active = useRef<AbortController | null>(null);
  const navigate = useNavigate();
  useEffect(() => () => active.current?.abort(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !isSourceId(sourceId)) return;
    setError("");
    if (format === "json") {
      const bytes = new TextEncoder().encode(text.replace(/\r\n?/g, "\n")).length;
      if (!text.trim()) { setError("Enter text to ingest."); textRef.current?.focus(); return; }
      if (bytes > MAX_TEXT_BYTES) { setError("Text must be 5,000,000 UTF-8 bytes or fewer."); textRef.current?.focus(); return; }
      if (filename.trim().length > 255 || /[/\\\0]/.test(filename) || [".", ".."].includes(filename.trim())) { setError("Use a valid filename of 255 characters or fewer."); textRef.current?.focus(); return; }
    } else {
      if (!file) { setError("Choose a file to ingest."); fileRef.current?.focus(); return; }
      const extension = file.name.toLowerCase().split(".").pop();
      const valid = format === "txt" ? extension === "txt" && ["", "text/plain"].includes(file.type) : extension === "pdf" && ["", "application/pdf"].includes(file.type);
      if (!valid) { setError(`Choose a valid ${format.toUpperCase()} file.`); fileRef.current?.focus(); return; }
      if (file.size === 0) { setError("The selected file is empty."); fileRef.current?.focus(); return; }
      if (file.size > MAX_UPLOAD_BYTES) { setError("The selected file must be 20,000,000 bytes or fewer."); fileRef.current?.focus(); return; }
    }
    const controller = new AbortController(); active.current?.abort(); active.current = controller; setSubmitting(true);
    try {
      const document = format === "json"
        ? await ingestSourceText(sourceId, { text, original_filename: filename.trim() || null, chunk_size: 2000, chunk_overlap: 200 }, controller.signal)
        : await ingestSourceFile(sourceId, (() => { const data = new FormData(); data.append("file", file as File); data.append("chunk_size", "2000"); data.append("chunk_overlap", "200"); return data; })(), controller.signal);
      navigate(`/source-documents/${document.id}`);
    } catch { if (!controller.signal.aborted) { setError("The document could not be ingested. Check the input and try again."); setSubmitting(false); } }
    finally { if (active.current === controller) active.current = null; }
  }

  if (!isSourceId(sourceId)) return <section className="panel"><h2>Invalid source address</h2><p>The source identifier is malformed.</p><Link to="/sources">Back to sources</Link></section>;
  return <><header className="page-header"><p className="eyebrow">Document ingestion</p><h1>Ingest a document</h1><p>Add JSON text, a TXT file, or a text-layer PDF to this Source.</p></header><section className="panel"><form onSubmit={submit} noValidate>
    <label htmlFor="document-format">Format</label><select ref={formatRef} id="document-format" value={format} disabled={submitting} onChange={(event) => { setFormat(event.target.value as Format); setFile(null); setError(""); }}><option value="json">JSON text</option><option value="txt">TXT file</option><option value="pdf">PDF file</option></select>
    {format === "json" ? <><label htmlFor="document-text">Document text</label><textarea ref={textRef} id="document-text" value={text} disabled={submitting} onChange={(event) => setText(event.target.value)} /><label htmlFor="original-filename">Original filename <span>(optional)</span></label><input id="original-filename" value={filename} disabled={submitting} onChange={(event) => setFilename(event.target.value)} /></> : <><label htmlFor="document-file">{format.toUpperCase()} file</label><input ref={fileRef} id="document-file" type="file" accept={format === "txt" ? ".txt,text/plain" : ".pdf,application/pdf"} disabled={submitting} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></>}
    {error && <p className="field-error" role="alert">{error}</p>}<button type="submit" disabled={submitting}>{submitting ? "Ingesting…" : "Ingest document"}</button>
  </form><Link className="back-link" to={`/sources/${sourceId}`}>Back to source</Link></section></>;
}

export function SourceDocumentDetail() {
  const { documentId = "" } = useParams();
  const valid = isSourceId(documentId);
  const [document, setDocument] = useState<SourceDocumentRead | null>(null);
  const [chunks, setChunks] = useState<SourceChunkRead[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error" | "missing" | "invalid">(valid ? "loading" : "invalid");
  const [offset, setOffset] = useState(0); const [attempt, setAttempt] = useState(0);
  const [generating, setGenerating] = useState(false); const [generationMessage, setGenerationMessage] = useState(""); const generation = useRef<AbortController | null>(null); const navigate = useNavigate();
  useEffect(() => {
    if (!valid) { setState("invalid"); return; }
    const controller = new AbortController(); setState("loading");
    Promise.all([getSourceDocument(documentId, controller.signal), listSourceChunks(documentId, CHUNK_PAGE_SIZE, offset, controller.signal)])
      .then(([item, page]) => { setDocument(item); setChunks(page); setState("ready"); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState(error instanceof SourceDocumentNotFoundError ? "missing" : "error"); });
    return () => controller.abort();
  }, [documentId, valid, offset, attempt]);
  useEffect(() => () => generation.current?.abort(), []);
  async function generate() { if (!document || generating || document.ingestion_status !== "extracted" || document.chunk_count === 0 || !window.confirm("Generate proposals from this document now?")) return; const controller = new AbortController(); generation.current = controller; setGenerating(true); setGenerationMessage(""); try { const result = await generateMemoryProposals(document.source_id, null, controller.signal); setGenerationMessage(`Generated ${result.proposal_count} proposal${result.proposal_count === 1 ? "" : "s"}.`); navigate(`/proposals?run=${result.id}`); } catch { if (!controller.signal.aborted) { setGenerationMessage("Proposal generation is unavailable. Check provider configuration and try again."); setGenerating(false); } } finally { if (generation.current === controller) generation.current = null; } }
  return <><header className="page-header"><p className="eyebrow">Source document</p><h1>Document detail</h1></header><section className="panel" aria-live="polite" aria-busy={state === "loading"}>
    {state === "loading" && <p>Loading document…</p>}{state === "invalid" && <><h2>Invalid document address</h2><p>The document identifier is malformed.</p></>}{state === "missing" && <><h2>Document not found</h2><p>The requested document does not exist.</p></>}{state === "error" && <><h2>Document unavailable</h2><p>The document could not be loaded.</p><button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button></>}
    {state === "ready" && document && <><dl className="detail-list"><div><dt>ID</dt><dd>{document.id}</dd></div><div><dt>Media type</dt><dd>{document.media_type}</dd></div><div><dt>Original filename</dt><dd>{document.original_filename ?? "Not supplied"}</dd></div><div><dt>Size</dt><dd>{document.byte_size === null ? "Not available" : `${document.byte_size} bytes`}</dd></div><div><dt>Extraction status</dt><dd>{document.ingestion_status}</dd></div><div><dt>Extracted</dt><dd>{timestamp(document.extracted_at)}</dd></div><div><dt>Created</dt><dd>{timestamp(document.created_at)}</dd></div><div><dt>Updated</dt><dd>{timestamp(document.updated_at)}</dd></div><div><dt>Chunks</dt><dd>{document.chunk_count}</dd></div></dl><section aria-labelledby="chunks-heading"><h2 id="chunks-heading">Extracted chunks</h2>{chunks.length === 0 ? <p>No chunks found.</p> : <ol className="chunk-list" start={offset + 1}>{chunks.map((chunk) => <li key={chunk.id}><p className="chunk-meta">Chunk {chunk.chunk_index}{chunk.locator ? ` · ${chunk.locator}` : ""} · characters {chunk.char_start}–{chunk.char_end}</p><pre>{chunk.content}</pre></li>)}</ol>}<nav className="pagination" aria-label="Chunk pages"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - CHUNK_PAGE_SIZE))}>Previous</button><span>Page {offset / CHUNK_PAGE_SIZE + 1}</span><button type="button" disabled={chunks.length < CHUNK_PAGE_SIZE} onClick={() => setOffset(offset + CHUNK_PAGE_SIZE)}>Next</button></nav></section><Link className="back-link" to={`/sources/${document.source_id}`}>Back to source</Link></>}
    {state === "ready" && document && <section aria-labelledby="generation-heading"><h2 id="generation-heading">Generate proposals</h2>{document.ingestion_status === "extracted" && document.chunk_count > 0 ? <><p>Explicitly run the configured extraction provider for this document’s Source.</p><button type="button" disabled={generating} onClick={generate}>{generating ? "Generating…" : "Generate proposals"}</button></> : <p>No usable extracted chunks are available. Ingest the document before generating proposals.</p>}{generationMessage && <p role="status">{generationMessage}</p>}</section>}
    {!document && <Link className="back-link" to="/sources">Back to sources</Link>}
  </section></>;
}
