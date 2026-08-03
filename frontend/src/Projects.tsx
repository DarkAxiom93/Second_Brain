import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  createProject,
  getProject,
  isProjectId,
  listProjects,
  ProjectNotFoundError,
  type ProjectRead,
} from "./api/client";

const PAGE_SIZE = 20;
type LoadState = "loading" | "ready" | "error";

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function Projects() {
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [offset, setOffset] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const submitController = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    listProjects(PAGE_SIZE, offset, controller.signal)
      .then((value) => { setProjects(value); setState("ready"); })
      .catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => controller.abort();
  }, [offset, attempt]);

  useEffect(() => () => submitController.current?.abort(), []);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    const trimmedName = name.trim();
    if (trimmedName.length < 1 || trimmedName.length > 200) {
      setNameError(trimmedName.length < 1 ? "Enter a project name." : "Use 200 characters or fewer.");
      nameRef.current?.focus();
      return;
    }
    setNameError("");
    setSubmitError("");
    setSubmitting(true);
    const trimmedDescription = description.trim();
    const controller = new AbortController();
    submitController.current = controller;
    try {
      const project = await createProject(
        { name: trimmedName, description: trimmedDescription || null },
        controller.signal,
      );
      navigate(`/projects/${project.id}`);
    } catch {
      if (!controller.signal.aborted) {
        setSubmitError("The project could not be created. Try again.");
        setSubmitting(false);
      }
    } finally {
      if (submitController.current === controller) submitController.current = null;
    }
  }

  return (
    <>
      <header className="page-header"><p className="eyebrow">Workspace</p><h1>Projects</h1><p>Create a project or open an existing one.</p></header>
      <section className="panel" aria-labelledby="create-project-heading">
        <h2 id="create-project-heading">Create a project</h2>
        <form onSubmit={submit} noValidate>
          <label htmlFor="project-name">Name</label>
          <input ref={nameRef} id="project-name" value={name} maxLength={201} aria-invalid={Boolean(nameError)} aria-describedby={nameError ? "project-name-error" : undefined} onChange={(event) => setName(event.target.value)} disabled={submitting} />
          {nameError && <p id="project-name-error" className="field-error" role="alert">{nameError}</p>}
          <label htmlFor="project-description">Description <span>(optional)</span></label>
          <textarea id="project-description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={submitting} />
          {submitError && <p className="field-error" role="alert">{submitError}</p>}
          <button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create project"}</button>
        </form>
      </section>
      <section className="panel" aria-labelledby="project-list-heading" aria-busy={state === "loading"}>
        <h2 id="project-list-heading">Project list</h2>
        <div aria-live="polite">
          {state === "loading" && <p>Loading projects…</p>}
          {state === "error" && <><p>Projects could not be loaded.</p><button type="button" onClick={retry}>Retry</button></>}
          {state === "ready" && projects.length === 0 && <p>No projects found.</p>}
          {state === "ready" && projects.length > 0 && <ul className="project-list">{projects.map((project) => <li key={project.id}><Link to={`/projects/${project.id}`}>{project.name}</Link>{project.description && <p>{project.description}</p>}</li>)}</ul>}
        </div>
        {state === "ready" && <nav className="pagination" aria-label="Project pages"><button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button><span>Page {offset / PAGE_SIZE + 1}</span><button type="button" disabled={projects.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button></nav>}
      </section>
    </>
  );
}

export function ProjectDetail() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [state, setState] = useState<LoadState | "missing" | "invalid">(isProjectId(projectId) ? "loading" : "invalid");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!isProjectId(projectId)) { setState("invalid"); return; }
    const controller = new AbortController();
    setState("loading");
    getProject(projectId, controller.signal)
      .then((value) => { setProject(value); setState("ready"); })
      .catch((error: unknown) => { if (!controller.signal.aborted) setState(error instanceof ProjectNotFoundError ? "missing" : "error"); });
    return () => controller.abort();
  }, [projectId, attempt]);

  return (
    <>
      <header className="page-header"><p className="eyebrow">Project detail</p><h1>{state === "ready" && project ? project.name : "Project"}</h1></header>
      <section className="panel" aria-live="polite" aria-busy={state === "loading"}>
        {state === "loading" && <p>Loading project…</p>}
        {state === "invalid" && <><h2>Invalid project address</h2><p>The project identifier is malformed.</p></>}
        {state === "missing" && <><h2>Project not found</h2><p>The requested project does not exist.</p></>}
        {state === "error" && <><h2>Project unavailable</h2><p>The project could not be loaded.</p><button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button></>}
        {state === "ready" && project && <dl className="detail-list"><div><dt>ID</dt><dd>{project.id}</dd></div><div><dt>Name</dt><dd>{project.name}</dd></div><div><dt>Description</dt><dd>{project.description ?? "No description"}</dd></div><div><dt>Created</dt><dd>{formatTimestamp(project.created_at)}</dd></div><div><dt>Updated</dt><dd>{formatTimestamp(project.updated_at)}</dd></div></dl>}
        <Link className="back-link" to="/projects">Back to projects</Link>
      </section>
    </>
  );
}
