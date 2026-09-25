import { FormEvent, KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  CaptureRevisionConflictError, type CaptureItem, type CaptureQuery, type CaptureScope, type CaptureState,
  convertCapture, createCapture, detailCapture, editCapture, listProjects, queryCaptures,
  reassignCapture, resolveCaptureSource, transitionCapture, type ProjectRead, type SourceRead,
} from "./api/client";

export const CAPTURE_CREATED_EVENT = "second-brain:capture-created";
const UNASSIGNED = "unassigned";
const scopeFrom = (value: string): CaptureScope => value === UNASSIGNED ? { unassigned: true } : { project_id: value };
const belongs = (item: CaptureItem, value: string) => value === UNASSIGNED ? item.project_id === null : item.project_id === value;
const idempotencyKey = () => crypto.randomUUID();
const editableTarget = (target: EventTarget | null) => {
  const element = target instanceof Element ? target : null;
  return Boolean(element?.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])"));
};

export function QuickCapture({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [content, setContent] = useState("");
  const [scopeValue, setScopeValue] = useState(UNASSIGNED);
  const [status, setStatus] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const logical = useRef<{ signature: string; key: string } | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { const controller = new AbortController(); listProjects(100, 0, controller.signal).then(setProjects).catch(() => setStatus("Projects could not be loaded; Unassigned remains available.")); return () => controller.abort(); }, []);
  useEffect(() => { contentRef.current?.focus(); }, []);
  const close = useCallback(() => { if (!submitting) onClose(); }, [onClose, submitting]);
  function keys(event: ReactKeyboardEvent) {
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key !== "Tab" || !dialog.current) return;
    const focusable = [...dialog.current.querySelectorAll<HTMLElement>("button:not(:disabled), textarea:not(:disabled), select:not(:disabled)")];
    if (!focusable.length) return;
    const first = focusable[0], last = focusable.at(-1)!;
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (submitting) return;
    if (!content.trim()) { setStatus("Enter capture text."); contentRef.current?.focus(); return; }
    const signature = JSON.stringify([content, scopeValue]);
    if (logical.current?.signature !== signature) logical.current = { signature, key: idempotencyKey() };
    setSubmitting(true); setStatus("Saving capture…");
    try {
      const item = await createCapture(content, scopeFrom(scopeValue), logical.current.key);
      setStatus("Capture saved."); setContent(""); logical.current = null;
      window.dispatchEvent(new CustomEvent(CAPTURE_CREATED_EVENT, { detail: { projectId: item.project_id } }));
      onSuccess(); onClose();
    } catch { setStatus("Capture could not be saved. Retry the unchanged draft safely."); }
    finally { setSubmitting(false); }
  }
  return <div className="modal-backdrop"><div ref={dialog} className="capture-modal" role="dialog" aria-modal="true" aria-labelledby="capture-title" onKeyDown={keys}>
    <h2 id="capture-title">Quick Capture</h2><p>Save a plain-text note to triage later.</p>
    <form onSubmit={submit}><label htmlFor="quick-content">Capture text</label><textarea ref={contentRef} id="quick-content" value={content} maxLength={8000} onChange={e => setContent(e.target.value)} disabled={submitting} />
      <label htmlFor="quick-scope">Exact scope</label><select id="quick-scope" value={scopeValue} onChange={e => setScopeValue(e.target.value)} disabled={submitting}><option value={UNASSIGNED}>Unassigned</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <p className="capture-status" role={status.includes("could not") ? "alert" : "status"} aria-live="polite">{status}</p>
      <div className="button-row"><button type="submit" disabled={submitting}>{submitting ? "Saving…" : "Save capture"}</button><button type="button" onClick={close} disabled={submitting}>Cancel</button></div>
    </form>
  </div></div>;
}

export function CaptureLauncher() {
  const [open, setOpen] = useState(false); const [announcement, setAnnouncement] = useState(""); const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => { setOpen(false); requestAnimationFrame(() => button.current?.focus()); }, []);
  const launch = useCallback(() => { setAnnouncement(""); setOpen(true); }, []);
  useEffect(() => { const handler = (event: globalThis.KeyboardEvent) => { if (open || event.isComposing || editableTarget(event.target)) return; if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "c") { event.preventDefault(); launch(); } }; document.addEventListener("keydown", handler); return () => document.removeEventListener("keydown", handler); }, [launch, open]);
  return <><button ref={button} type="button" className="capture-launcher" onClick={launch} aria-keyshortcuts="Control+Shift+C">+ Capture</button><p className="capture-status" role="status" aria-live="polite">{announcement}</p>{open && <QuickCapture onClose={close} onSuccess={() => setAnnouncement("Capture saved.")} />}</>;
}

export function CaptureInbox() {
  const [projects, setProjects] = useState<ProjectRead[]>([]); const [scopeValue, setScopeValue] = useState(UNASSIGNED); const [state, setState] = useState<CaptureState>("pending");
  const [search, setSearch] = useState(""); const [appliedSearch, setAppliedSearch] = useState(""); const [requestAttempt, setRequestAttempt] = useState(0); const [items, setItems] = useState<CaptureItem[]>([]); const [next, setNext] = useState<string | null>(null); const [stack, setStack] = useState<Array<string | undefined>>([]);
  const [selected, setSelected] = useState<CaptureItem | null>(null); const [source, setSource] = useState<SourceRead | null>(null); const [message, setMessage] = useState(""); const [loading, setLoading] = useState(false); const [edit, setEdit] = useState(""); const [target, setTarget] = useState(UNASSIGNED);
  const snapshot = useRef({ scopeValue, state, appliedSearch }); snapshot.current = { scopeValue, state, appliedSearch };
  const generation = useRef(0); const loadController = useRef<AbortController | null>(null);
  const invalidate = useCallback(() => { generation.current += 1; loadController.current?.abort(); setNext(null); setStack([]); setSelected(null); setSource(null); }, []);
  const load = useCallback(async (cursor?: string, direction?: "next" | "previous") => { const requestGeneration = ++generation.current; loadController.current?.abort(); const controller = new AbortController(); loadController.current = controller; setNext(null); setLoading(true); setMessage("Loading captures…"); const current = snapshot.current; const request: CaptureQuery = { scope: scopeFrom(current.scopeValue), states: [current.state], page_size: 25, ...(current.appliedSearch ? { query: current.appliedSearch } : {}), ...(cursor ? { cursor } : {}) }; try { const page = await queryCaptures(request, controller.signal); if (requestGeneration !== generation.current) return; setItems(page.items); setNext(page.next_cursor); setSelected(null); setSource(null); if (direction === "next") setStack(s => [...s, cursor]); else if (direction === "previous") setStack(s => s.slice(0, -1)); setMessage(page.items.length ? `${page.items.length} capture${page.items.length === 1 ? "" : "s"} loaded.` : "No captures in this exact view."); } catch { if (!controller.signal.aborted && requestGeneration === generation.current) setMessage("Captures could not be loaded."); } finally { if (requestGeneration === generation.current) { setLoading(false); loadController.current = null; } } }, []);
  useEffect(() => { const controller = new AbortController(); listProjects(100, 0, controller.signal).then(setProjects).catch(() => setMessage("Projects could not be loaded.")); return () => controller.abort(); }, []);
  useEffect(() => { setStack([]); void load(); }, [scopeValue, state, appliedSearch, requestAttempt, load]);
  useEffect(() => () => { generation.current += 1; loadController.current?.abort(); }, []);
  useEffect(() => { const handler = (event: Event) => { const projectId = (event as CustomEvent<{projectId: string | null}>).detail.projectId; if (state === "pending" && !appliedSearch && ((scopeValue === UNASSIGNED && projectId === null) || scopeValue === projectId)) void load(); }; window.addEventListener(CAPTURE_CREATED_EVENT, handler); return () => window.removeEventListener(CAPTURE_CREATED_EVENT, handler); }, [state, appliedSearch, scopeValue, load]);
  async function select(item: CaptureItem) { setMessage("Loading exact capture…"); try { const found = await detailCapture(item.id, scopeFrom(scopeValue)); setSelected(found); setEdit(found.content); setTarget(found.project_id ?? UNASSIGNED); setSource(null); setMessage("Exact capture loaded."); } catch { setMessage("The capture could not be opened in this scope."); } }
  const reconcile = (item: CaptureItem) => { const sameScope = belongs(item, scopeValue); const remains = sameScope && item.state === state; setSelected(sameScope ? item : null); setEdit(item.content); if (!remains) setItems(xs => xs.filter(x => x.id !== item.id)); else setItems(xs => xs.map(x => x.id === item.id ? item : x)); };
  async function mutate(action: () => Promise<CaptureItem>) { try { const item = await action(); reconcile(item); setMessage("Capture updated."); } catch (error) { if (error instanceof CaptureRevisionConflictError) { reconcile(error.item); setMessage("This item changed; refreshed. Review it before retrying."); } else setMessage("The action could not be completed."); } }
  async function convert() { if (!selected) return; try { const result = await convertCapture(selected.id, scopeFrom(scopeValue), selected.revision); reconcile(result.capture); setSource(result.source); setMessage("Capture converted to an audited Source."); } catch (error) { if (error instanceof CaptureRevisionConflictError) { reconcile(error.item); setMessage("This item changed; refreshed. Review it before retrying."); } else setMessage("The action could not be completed."); } }
  async function reopen() { if (!selected) return; try { setSource(await resolveCaptureSource(selected.id, scopeFrom(scopeValue))); setMessage("Scoped Source reopened."); } catch { setMessage("The Source could not be reopened in this scope."); } }
  function submitSearch(event: FormEvent) { event.preventDefault(); invalidate(); setAppliedSearch(search.trim()); setRequestAttempt(value => value + 1); }
  return <><header className="page-header"><p className="eyebrow">Triage</p><h1>Capture Inbox</h1><p>Browse and act on one exact scope at a time.</p></header>
    <section className="panel"><form onSubmit={submitSearch}><label htmlFor="inbox-scope">Exact scope</label><select id="inbox-scope" value={scopeValue} onChange={e => { invalidate(); setScopeValue(e.target.value); }}><option value={UNASSIGNED}>Unassigned</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
      <label htmlFor="inbox-state">State</label><select id="inbox-state" value={state} onChange={e => { invalidate(); setState(e.target.value as CaptureState); }}><option value="pending">Pending</option><option value="discarded">Discarded</option><option value="processed">Processed</option></select>
      <label htmlFor="inbox-search">Lexical search</label><input id="inbox-search" value={search} maxLength={200} onChange={e => setSearch(e.target.value)} /><div className="button-row"><button type="submit">Search</button><button type="button" onClick={() => { invalidate(); setSearch(""); setAppliedSearch(""); setRequestAttempt(value => value + 1); }}>Clear search</button></div></form>
    </section><p className="capture-status" role={message.includes("could not") ? "alert" : "status"} aria-live="polite">{message}</p>
    <section className="panel" aria-labelledby="capture-list-heading" aria-busy={loading}><h2 id="capture-list-heading">{state[0].toUpperCase() + state.slice(1)} captures</h2><ul className="capture-list">{items.map(item => <li key={item.id}><button type="button" onClick={() => void select(item)}><span className="hostile-text" dir="auto">{item.content}</span><small>Revision {item.revision}</small></button></li>)}</ul><div className="button-row">{stack.length > 0 && <button type="button" onClick={() => void load(stack.at(-2), "previous")}>Previous page</button>}{next && <button type="button" onClick={() => void load(next, "next")}>Next page</button>}</div></section>
    {selected && <section className="panel capture-detail" aria-labelledby="capture-detail-heading"><h2 id="capture-detail-heading">Capture detail</h2><p className="hostile-text" dir="auto">{selected.content}</p><dl><div><dt>State</dt><dd>{selected.state}</dd></div><div><dt>Revision</dt><dd>{selected.revision}</dd></div></dl>
      {selected.state === "pending" && <><label htmlFor="capture-edit">Edit plain text</label><textarea id="capture-edit" value={edit} maxLength={8000} onChange={e => setEdit(e.target.value)} /><button type="button" onClick={() => void mutate(() => editCapture(selected.id, scopeFrom(scopeValue), selected.revision, edit))}>Save edit</button>
        <label htmlFor="capture-target">Reassign to</label><select id="capture-target" value={target} onChange={e => setTarget(e.target.value)}><option value={UNASSIGNED}>Unassigned</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><button type="button" onClick={() => void mutate(() => reassignCapture(selected.id, scopeFrom(scopeValue), scopeFrom(target), selected.revision))}>Reassign</button>
        <button type="button" onClick={() => void mutate(() => transitionCapture(selected.id, "discard", scopeFrom(scopeValue), selected.revision))}>Discard</button><button type="button" onClick={() => void convert()}>Convert to Source</button></>}
      {selected.state === "discarded" && <button type="button" onClick={() => void mutate(() => transitionCapture(selected.id, "restore", scopeFrom(scopeValue), selected.revision))}>Restore</button>}
      {selected.state === "processed" && <button type="button" onClick={() => void reopen()}>Reopen scoped Source</button>}
      {source && <article aria-labelledby="resolved-source"><h3 id="resolved-source">Authorized Source</h3><p className="hostile-text" dir="auto">{source.name}</p><dl><div><dt>Type</dt><dd>{source.source_type}</dd></div><div><dt>Created</dt><dd>{new Date(source.created_at).toLocaleString()}</dd></div></dl></article>}
    </section>}</>;
}
