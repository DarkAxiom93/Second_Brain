import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  createSource, getSource, isSourceId, listSourceDocuments, listSourceMemories, listSources,
  SourceNotFoundError, type LinkedMemoryRead, type SourceDocumentRead, type SourceRead,
} from "./api/client";

const PAGE_SIZE = 20;
type LoadState = "loading" | "ready" | "error";

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function Sources() {
  const [sources, setSources] = useState<SourceRead[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [sourceType, setSourceType] = useState("");
  const [name, setName] = useState("");
  const [reference, setReference] = useState("");
  const [checksum, setChecksum] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const typeRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const checksumRef = useRef<HTMLInputElement>(null);
  const submitController = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    listSources(PAGE_SIZE, offset, controller.signal)
      .then((value) => { setSources(value); setState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => controller.abort();
  }, [offset, attempt]);
  useEffect(() => () => submitController.current?.abort(), []);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const typeValue = sourceType.trim();
    const nameValue = name.trim();
    const checksumValue = checksum.trim();
    const nextErrors: Record<string, string> = {};
    if (typeValue.length < 1 || typeValue.length > 50) nextErrors.sourceType = typeValue ? "Use 50 characters or fewer." : "Enter a source type.";
    if (nameValue.length < 1 || nameValue.length > 255) nextErrors.name = nameValue ? "Use 255 characters or fewer." : "Enter a source name.";
    if (checksumValue.length > 64) nextErrors.checksum = "Use 64 characters or fewer.";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      if (nextErrors.sourceType) typeRef.current?.focus();
      else if (nextErrors.name) nameRef.current?.focus();
      else checksumRef.current?.focus();
      return;
    }
    setSubmitError("");
    setSubmitting(true);
    const controller = new AbortController();
    submitController.current = controller;
    try {
      const source = await createSource({
        source_type: typeValue, name: nameValue,
        reference: reference.trim() || null, checksum: checksumValue || null,
      }, controller.signal);
      navigate(`/sources/${source.id}`);
    } catch {
      if (!controller.signal.aborted) {
        setSubmitError("The source could not be created. Try again.");
        setSubmitting(false);
      }
    } finally {
      if (submitController.current === controller) submitController.current = null;
    }
  }

  const field = (id: string, label: string, value: string, setter: (value: string) => void, ref?: React.RefObject<HTMLInputElement | null>, optional = false) => (
    <><label htmlFor={id}>{label} {optional && <span>(optional)</span>}</label><input ref={ref} id={id} value={value} disabled={submitting} aria-invalid={Boolean(errors[id])} aria-describedby={errors[id] ? `${id}-error` : undefined} onChange={(event) => setter(event.target.value)} />{errors[id] && <p id={`${id}-error`} className="field-error" role="alert">{errors[id]}</p>}</>
  );

  return <>
    <header className="page-header"><p className="eyebrow">Provenance</p><h1>Sources</h1><p>Create a source or inspect existing provenance.</p></header>
    <section className="panel" aria-labelledby="create-source-heading"><h2 id="create-source-heading">Create a source</h2><form onSubmit={submit} noValidate>
      {field("sourceType", "Source type", sourceType, setSourceType, typeRef)}
      {field("name", "Name", name, setName, nameRef)}
      {field("reference", "Reference", reference, setReference, undefined, true)}
      {field("checksum", "Checksum", checksum, setChecksum, checksumRef, true)}
      {submitError && <p className="field-error" role="alert">{submitError}</p>}
      <button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create source"}</button>
    </form></section>
    <section className="panel" aria-labelledby="source-list-heading" aria-busy={state === "loading"}><h2 id="source-list-heading">Source list</h2><div aria-live="polite">
      {state === "loading" && <p>Loading sources…</p>}
      {state === "error" && <><p>Sources could not be loaded.</p><button type="button" onClick={retry}>Retry</button></>}
      {state === "ready" && sources.length === 0 && <p>No sources found.</p>}
      {state === "ready" && sources.length > 0 && <ul className="project-list">{sources.map((source) => <li key={source.id}><Link to={`/sources/${source.id}`}>{source.name}</Link><p>{source.source_type}</p></li>)}</ul>}
    </div>{state === "ready" && <nav className="pagination" aria-label="Source pages"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button><span>Page {offset / PAGE_SIZE + 1}</span><button type="button" disabled={sources.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></nav>}</section>
  </>;
}

export function SourceDetail() {
  const { sourceId = "" } = useParams();
  const [source, setSource] = useState<SourceRead | null>(null);
  const [memories, setMemories] = useState<LinkedMemoryRead[]>([]);
  const [documents, setDocuments] = useState<SourceDocumentRead[]>([]);
  const [documentOffset, setDocumentOffset] = useState(0);
  const [state, setState] = useState<LoadState | "missing" | "invalid">(isSourceId(sourceId) ? "loading" : "invalid");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!isSourceId(sourceId)) { setState("invalid"); return; }
    const controller = new AbortController();
    setState("loading");
    Promise.all([getSource(sourceId, controller.signal), listSourceMemories(sourceId, controller.signal), listSourceDocuments(sourceId, PAGE_SIZE, documentOffset, controller.signal)])
      .then(([value, links, page]) => { setSource(value); setMemories(links); setDocuments(page); setState("ready"); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState(error instanceof SourceNotFoundError ? "missing" : "error"); });
    return () => controller.abort();
  }, [sourceId, attempt, documentOffset]);
  return <><header className="page-header"><p className="eyebrow">Source detail</p><h1>{state === "ready" && source ? source.name : "Source"}</h1></header><section className="panel" aria-live="polite" aria-busy={state === "loading"}>
    {state === "loading" && <p>Loading source…</p>}
    {state === "invalid" && <><h2>Invalid source address</h2><p>The source identifier is malformed.</p></>}
    {state === "missing" && <><h2>Source not found</h2><p>The requested source does not exist.</p></>}
    {state === "error" && <><h2>Source unavailable</h2><p>The source could not be loaded.</p><button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button></>}
    {state === "ready" && source && <><dl className="detail-list"><div><dt>ID</dt><dd>{source.id}</dd></div><div><dt>Name</dt><dd>{source.name}</dd></div><div><dt>Source type</dt><dd>{source.source_type}</dd></div><div><dt>Reference</dt><dd>{source.reference ?? "No reference"}</dd></div><div><dt>Checksum</dt><dd>{source.checksum ?? "No checksum"}</dd></div><div><dt>Created</dt><dd>{formatTimestamp(source.created_at)}</dd></div><div><dt>Updated</dt><dd>{formatTimestamp(source.updated_at)}</dd></div></dl><Link className="action-link" to={`/sources/${source.id}/ingest`}>Ingest document</Link><section aria-labelledby="documents-heading"><h2 id="documents-heading">Documents</h2>{documents.length === 0 ? <p>No documents ingested.</p> : <ul className="project-list">{documents.map((document) => <li key={document.id}><Link to={`/source-documents/${document.id}`}>{document.original_filename ?? `Document ${document.id}`}</Link><p>{document.media_type} · {document.ingestion_status} · {document.chunk_count} chunks</p></li>)}</ul>}<nav className="pagination" aria-label="Document pages"><button type="button" disabled={documentOffset === 0} onClick={() => setDocumentOffset(Math.max(0, documentOffset - PAGE_SIZE))}>Previous</button><span>Page {documentOffset / PAGE_SIZE + 1}</span><button type="button" disabled={documents.length < PAGE_SIZE} onClick={() => setDocumentOffset(documentOffset + PAGE_SIZE)}>Next</button></nav></section><section aria-labelledby="linked-memories-heading"><h2 id="linked-memories-heading">Linked memories</h2>{memories.length === 0 ? <p>No linked memories.</p> : <ul className="relationship-list">{memories.map((memory) => <li key={memory.link_id}>{memory.title ?? `Memory ${memory.memory_id}`} {memory.source_location && <span>— {memory.source_location}</span>}</li>)}</ul>}</section></>}
    <Link className="back-link" to="/sources">Back to sources</Link>
  </section></>;
}
