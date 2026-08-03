import { FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { AnswerProviderError, createAnswer, isProjectId, type AnswerRead, type AnswerRequest, type SearchMode } from "./api/client";

type State = "idle" | "loading" | "ready" | "error";

export function Answers() {
  const [question, setQuestion] = useState("");
  const [projectId, setProjectId] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [limit, setLimit] = useState("10");
  const [state, setState] = useState<State>("idle");
  const [answer, setAnswer] = useState<AnswerRead | null>(null);
  const [lastRequest, setLastRequest] = useState<AnswerRequest | null>(null);
  const [error, setError] = useState("");
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const projectRef = useRef<HTMLInputElement>(null);
  const limitRef = useRef<HTMLInputElement>(null);
  const answerHeadingRef = useRef<HTMLHeadingElement>(null);
  const active = useRef<AbortController | null>(null);
  const activeRequest = useRef<AnswerRequest | null>(null);
  const sequence = useRef(0);

  useEffect(() => () => active.current?.abort(), []);

  function validate(): AnswerRequest | null {
    const query = question.trim();
    const project = projectId.trim();
    const amount = Number(limit);
    if (!query || query.length > 500) {
      setError(query ? "Question must be at most 500 characters." : "Enter a question.");
      setTimeout(() => questionRef.current?.focus(), 0);
      return null;
    }
    if (project && !isProjectId(project)) {
      setError("Enter a valid Project UUID.");
      setTimeout(() => projectRef.current?.focus(), 0);
      return null;
    }
    if (!Number.isInteger(amount) || amount < 1 || amount > 20) {
      setError("Limit must be a whole number from 1 to 20.");
      setTimeout(() => limitRef.current?.focus(), 0);
      return null;
    }
    return { query, project_id: project || null, search_mode: mode, limit: amount };
  }

  async function run(request: AnswerRequest) {
    const token = ++sequence.current;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    activeRequest.current = request;
    setState("loading");
    setError("");
    setLastRequest(request);
    try {
      const value = await createAnswer(request, controller.signal);
      if (token !== sequence.current) return;
      setAnswer(value);
      setState("ready");
      setTimeout(() => answerHeadingRef.current?.focus(), 0);
    } catch (reason) {
      if (token !== sequence.current || controller.signal.aborted) return;
      setError(reason instanceof AnswerProviderError ? reason.message : "The answer could not be completed safely.");
      setState("error");
    } finally {
      if (active.current === controller) activeRequest.current = null;
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request = validate();
    if (state === "loading" && request && JSON.stringify(request) === JSON.stringify(activeRequest.current)) return;
    if (request) void run(request);
  }

  return <>
    <header className="page-header"><p className="eyebrow">Evidence-backed answers</p><h1>Answers</h1><p>Ask one explicit question over bounded, active Memory evidence.</p></header>
    <section className="panel" aria-labelledby="answer-form-heading"><h2 id="answer-form-heading">Ask a question</h2>
      <form onSubmit={submit} noValidate>
        <label htmlFor="answer-project">Project UUID <span>(optional; blank searches unassigned Memories)</span></label>
        <input ref={projectRef} id="answer-project" value={projectId} onChange={event => setProjectId(event.target.value)} aria-invalid={error === "Enter a valid Project UUID."} />
        <label htmlFor="answer-question">Question</label>
        <textarea ref={questionRef} id="answer-question" value={question} maxLength={501} onChange={event => setQuestion(event.target.value)} />
        <div className="search-grid"><div><label htmlFor="answer-mode">Retrieval mode</label><select id="answer-mode" value={mode} onChange={event => setMode(event.target.value as SearchMode)}><option value="lexical">Lexical</option><option value="semantic">Semantic</option><option value="hybrid">Hybrid (RRF)</option></select></div><div><label htmlFor="answer-limit">Evidence limit</label><input ref={limitRef} id="answer-limit" type="number" min="1" max="20" value={limit} onChange={event => setLimit(event.target.value)} /></div></div>
        {error && state !== "error" && <p className="field-error" role="alert">{error}</p>}
        <button type="submit" disabled={state === "loading"}>{state === "loading" ? "Answering…" : "Submit question"}</button>
      </form>
    </section>
    <section className="panel answer-region" aria-labelledby="answer-heading" aria-busy={state === "loading"} aria-live="polite">
      <h2 ref={answerHeadingRef} tabIndex={-1} id="answer-heading">Answer</h2>
      {state === "idle" && <p>Submit the form to request an answer. Editing fields does not run or replace an answer.</p>}
      {state === "loading" && <p role="status">Retrieving evidence and preparing an answer…</p>}
      {state === "error" && <><p role="alert">{error}</p><button type="button" onClick={() => lastRequest && void run(lastRequest)}>Retry last submitted question</button></>}
      {state === "ready" && answer && <><p className="chunk-meta">Status: {answer.answer_status === "answered" ? "Answered" : "Insufficient evidence"} · Retrieval mode: {answer.search_mode}</p><div className="answer-text">{answer.answer}</div><section aria-labelledby="answer-evidence-heading"><h3 id="answer-evidence-heading">Supporting evidence</h3>{answer.citations.length === 0 ? <p>No supporting evidence was returned.</p> : <ol className="memory-list answer-evidence">{answer.citations.map(citation => <li key={`${citation.rank}-${citation.memory.id}`}><p className="chunk-meta">{citation.label} · Retrieval rank {citation.rank}</p><h4><Link to={`/memories/${citation.memory.id}`}>{citation.memory.title ?? `Memory ${citation.memory.id}`}</Link></h4><pre className="evidence">{citation.memory.content}</pre><p className="chunk-meta">Lexical score: {citation.lexical_score ?? "Not returned"} · Semantic score: {citation.semantic_score ?? "Not returned"}</p></li>)}</ol>}</section></>}
    </section>
  </>;
}
