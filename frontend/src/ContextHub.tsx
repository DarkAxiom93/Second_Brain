import { FormEvent, useEffect, useRef, useState } from "react";
import { ContextFacetLimitError, detailContextHub, facetContextHub, listProjects, queryContextHub, type ContextFamily, type ContextHubFacets, type ContextHubItem, type ContextHubPage, type ContextHubQuery, type ContextKind, type ContextState, type ContextTrust, type ProjectRead } from "./api/client";

const FAMILIES: ContextFamily[] = ["local_source", "github", "google_calendar"];
const KINDS: ContextKind[] = ["source_chunk", "repository", "issue", "pull_request", "calendar_event"];
const TRUST: ContextTrust[] = ["local_audited", "quarantined_external"];
const STATES: ContextState[] = ["extracted", "current", "stale", "deleted"];
const LABEL: Record<string, string> = { local_source: "Local source", github: "GitHub", google_calendar: "Google Calendar", source_chunk: "Source chunk", repository: "Repository", issue: "Issue", pull_request: "Pull request", calendar_event: "Calendar event", local_audited: "Local audited", quarantined_external: "Quarantined external", extracted: "Extracted", current: "Current", stale: "Stale", deleted: "Deleted" };
const PROVENANCE: Record<ContextFamily, string> = { local_source: "Exact audited Source → Document → Chunk.", github: "Exact GitHub immutable item revision and application history.", google_calendar: "Exact Calendar occurrence and revision with application observation evidence." };
type LoadState = "idle" | "loading" | "ready" | "error";
const display = (value: string) => LABEL[value] ?? value.replaceAll("_", " ");

export function ContextHub() {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [projectsState, setProjectsState] = useState<"loading" | "ready" | "error">("loading");
  const [scope, setScope] = useState("");
  const [query, setQuery] = useState("");
  const [families, setFamilies] = useState(FAMILIES);
  const [kinds, setKinds] = useState<ContextKind[]>([]);
  const [trust, setTrust] = useState<ContextTrust[]>([]);
  const [states, setStates] = useState<ContextState[]>([]);
  const [pageSize, setPageSize] = useState(20);
  const [applied, setApplied] = useState<ContextHubQuery | null>(null);
  const [page, setPage] = useState<ContextHubPage | null>(null);
  const [facets, setFacets] = useState<ContextHubFacets | null>(null);
  const [facetLimited, setFacetLimited] = useState(false);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [message, setMessage] = useState("Select an exact scope, then choose Search context.");
  const [detail, setDetail] = useState<ContextHubItem | null>(null);
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const closeRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef<HTMLButtonElement | null>(null);
  const active = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listProjects(100, 0, controller.signal).then((value) => { setProjects(value); setProjectsState("ready"); }).catch(() => { if (!controller.signal.aborted) setProjectsState("error"); });
    return () => controller.abort();
  }, []);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => { if (detailState === "ready") closeRef.current?.focus(); }, [detailState]);

  function invalidate() {
    active.current?.abort(); setApplied(null); setPage(null); setFacets(null); setFacetLimited(false); setDetail(null); setDetailState("idle"); setLoadState("idle");
    setMessage("Controls changed. Choose Search context to apply them.");
  }
  function toggle<T extends string>(value: T, values: T[], setter: (next: T[]) => void) {
    invalidate(); setter(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  }
  function snapshot(): ContextHubQuery | null {
    if (!scope || families.length === 0) return null;
    return { scope: scope === "unassigned" ? { project_id: null, unassigned: true } : { project_id: scope, unassigned: false }, families: [...families], kinds: [...kinds], trust: [...trust], states: [...states], query: query.trim(), page_size: pageSize };
  }
  async function load(request: ContextHubQuery, cursor?: string) {
    const controller = new AbortController(); active.current = controller; setLoadState("loading");
    setMessage(cursor ? "Loading next page…" : "Searching context and loading exact facets…");
    if (!cursor) { setFacets(null); setFacetLimited(false); }
    try {
      const pagePromise = queryContextHub({ ...request, ...(cursor ? { cursor } : {}) }, controller.signal);
      const facetsPromise = cursor ? null : facetContextHub(request, controller.signal);
      const next = await pagePromise; setPage(next);
      if (facetsPromise) {
        try { setFacets(await facetsPromise); }
        catch (error) { if (error instanceof ContextFacetLimitError) setFacetLimited(true); else throw error; }
      }
      setLoadState("ready"); setMessage(next.groups.some((group) => group.items.length) ? "Context results loaded." : "No context matched this request.");
    } catch { if (!controller.signal.aborted) { setLoadState("error"); setMessage("Context could not be loaded. No private error details were displayed."); } }
    finally { if (active.current === controller) active.current = null; }
  }
  function submit(event: FormEvent) {
    event.preventDefault(); const next = snapshot();
    if (!next) { setMessage(scope ? "Select at least one family." : "Select one Project or explicit unassigned scope."); return; }
    if (new TextEncoder().encode(next.query).length > 768) { setMessage("Query must be no more than 768 UTF-8 bytes."); return; }
    const selected = new Set(next.families);
    const kindFamily: Record<ContextKind, ContextFamily> = { source_chunk: "local_source", repository: "github", issue: "github", pull_request: "github", calendar_event: "google_calendar" };
    const eligible = next.families.filter((family) =>
      (!next.kinds.length || next.kinds.some((kind) => kindFamily[kind] === family)) &&
      (!next.trust.length || next.trust.some((value) => value === "local_audited" ? family === "local_source" : family !== "local_source")) &&
      (!next.states.length || next.states.some((value) => value === "extracted" ? family === "local_source" : value === "deleted" ? family === "github" : family !== "local_source")),
    );
    if (!eligible.length || next.kinds.some((kind) => !selected.has(kindFamily[kind]))) { setMessage("Selected filters are not compatible with the selected families."); return; }
    setApplied(next); void load(next);
  }
  async function openDetail(item: ContextHubItem, button: HTMLButtonElement) {
    if (!applied) return;
    returnFocus.current = button; setDetail(null); setDetailState("loading");
    const controller = new AbortController(); active.current = controller;
    try { setDetail(await detailContextHub({ scope: applied.scope, family: item.family, reopen_id: item.reopen_id }, controller.signal)); setDetailState("ready"); }
    catch { if (!controller.signal.aborted) setDetailState("error"); }
  }
  function closeDetail() { setDetail(null); setDetailState("idle"); returnFocus.current?.focus(); }
  const scopeLabel = applied?.scope.unassigned ? "Explicit unassigned" : projects.find((project) => project.id === applied?.scope.project_id)?.name ?? "Selected Project";

  return <>
    <header className="page-header"><p className="eyebrow">Read-only context</p><h1>Context Hub</h1><p>Search exact Project or unassigned context across audited local sources and quarantined external families.</p></header>
    <section className="panel context-controls" aria-labelledby="hub-search"><h2 id="hub-search">Search context</h2><form onSubmit={submit}>
      <label htmlFor="hub-scope">Exact scope</label><select id="hub-scope" value={scope} disabled={projectsState === "loading"} onChange={(event) => { invalidate(); setScope(event.target.value); }}><option value="">Select a scope…</option><option value="unassigned">Explicit unassigned</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
      {projectsState === "loading" && <p role="status">Loading Projects…</p>}{projectsState === "error" && <p role="alert">Projects could not be loaded. Explicit unassigned remains available.</p>}
      <label htmlFor="hub-query">Text query <span>(optional, 256 characters)</span></label><input id="hub-query" maxLength={256} value={query} onChange={(event) => { invalidate(); setQuery(event.target.value); }} />
      <fieldset><legend>Families</legend>{FAMILIES.map((value) => <label key={value}><input type="checkbox" checked={families.includes(value)} onChange={() => toggle(value, families, setFamilies)} />{display(value)}</label>)}</fieldset>
      <fieldset><legend>Kinds <span>(optional)</span></legend>{KINDS.map((value) => <label key={value}><input type="checkbox" checked={kinds.includes(value)} onChange={() => toggle(value, kinds, setKinds)} />{display(value)}</label>)}</fieldset>
      <fieldset><legend>Trust <span>(optional)</span></legend>{TRUST.map((value) => <label key={value}><input type="checkbox" checked={trust.includes(value)} onChange={() => toggle(value, trust, setTrust)} />{display(value)}</label>)}</fieldset>
      <fieldset><legend>Native state <span>(optional)</span></legend>{STATES.map((value) => <label key={value}><input type="checkbox" checked={states.includes(value)} onChange={() => toggle(value, states, setStates)} />{display(value)}</label>)}</fieldset>
      <label htmlFor="hub-size">Results per family</label><select id="hub-size" value={pageSize} onChange={(event) => { invalidate(); setPageSize(Number(event.target.value)); }}>{[10, 20, 50].map((value) => <option key={value}>{value}</option>)}</select>
      <button type="submit" disabled={loadState === "loading"}>Search context</button>
    </form></section>
    <p className="hub-status" role={loadState === "error" ? "alert" : "status"} aria-live="polite">{message}</p>
    {applied && <section className="panel context-results" aria-labelledby="hub-results" aria-busy={loadState === "loading"}><h2 id="hub-results">Results</h2><p><strong>Applied scope:</strong> {scopeLabel}</p>
      {page && FAMILIES.map((family) => { const group = page.groups.find((value) => value.family === family); if (!group) return null; return <section className="context-group" key={family} aria-labelledby={`group-${family}`}><h3 id={`group-${family}`}>{display(family)}</h3><p>{PROVENANCE[family]}</p>{group.items.length === 0 ? <p>No results in this family.</p> : <ul className="context-list">{group.items.map((item, index) => <li key={`${item.family}-${index}`}><article><h4 className="hostile-text" dir="auto">{item.title}</h4><p className="hostile-text" dir="auto">{item.text}</p><Disclosure item={item} scopeLabel={scopeLabel} /><button type="button" onClick={(event) => void openDetail(item, event.currentTarget)}>Open exact {display(item.kind)} detail</button></article></li>)}</ul>}</section>; })}
      {page?.next_cursor && <button type="button" onClick={() => void load(applied, page.next_cursor!)} disabled={loadState === "loading"}>Load next page</button>}
    </section>}
    {applied && <section className="panel" aria-labelledby="facet-heading"><h2 id="facet-heading">Facet counts</h2>{facetLimited && <p>Counts unavailable for this request because the exact backend work bound was exceeded.</p>}{facets && <><p>Request-time observation: <time dateTime={facets.observed_at}>{new Date(facets.observed_at).toLocaleString()}</time></p>{([["Family", facets.families], ["Kind", facets.kinds], ["Trust", facets.trust], ["State", facets.states]] as const).map(([name, buckets]) => <div key={name}><h3>{name}</h3><dl className="count-grid">{buckets.map((bucket) => <div key={bucket.value}><dt>{display(bucket.value)}</dt><dd>{bucket.count}</dd></div>)}</dl></div>)}</>}</section>}
    {detailState !== "idle" && <section className="panel context-detail" aria-labelledby="detail-heading" aria-busy={detailState === "loading"}><h2 id="detail-heading">Exact context detail</h2>{detailState === "loading" && <p role="status">Loading exact detail…</p>}{detailState === "error" && <p role="alert">This exact item could not be reopened.</p>}{detail && <><h3 className="hostile-text" dir="auto">{detail.title}</h3><p className="hostile-text" dir="auto">{detail.text}</p><Disclosure item={detail} scopeLabel={scopeLabel} /></>}<button ref={closeRef} type="button" onClick={closeDetail}>Close detail and return to result</button></section>}
  </>;
}

function Disclosure({ item, scopeLabel }: { item: ContextHubItem; scopeLabel: string }) {
  return <dl className="context-disclosure"><div><dt>Family</dt><dd>{display(item.family)}</dd></div><div><dt>Kind</dt><dd>{display(item.kind)}</dd></div><div><dt>Trust</dt><dd>{display(item.trust)}</dd></div><div><dt>Native state</dt><dd>{display(item.state)}</dd></div><div><dt>Exact scope</dt><dd>{scopeLabel}</dd></div><div><dt>Provenance</dt><dd>{PROVENANCE[item.family]}</dd></div></dl>;
}
