import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectDetail, Projects } from "./Projects";

const project = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Pure Axiom",
  description: "Interactive mathematics platform",
  created_at: "2026-07-31T10:00:00Z",
  updated_at: "2026-07-31T11:00:00Z",
};

function jsonResponse(body: unknown, ok = true, status = ok ? 200 : 503): Response {
  return { ok, status, json: vi.fn().mockResolvedValue(body) } as unknown as Response;
}

function renderProjects() {
  return render(<MemoryRouter><Routes><Route path="/" element={<Projects />} /><Route path="/projects/:projectId" element={<p>Created project page</p>} /></Routes></MemoryRouter>);
}

function renderDetail(id = project.id) {
  return render(<MemoryRouter initialEntries={[`/projects/${id}`]}><Routes><Route path="/projects/:projectId" element={<ProjectDetail />} /></Routes></MemoryRouter>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("project list", () => {
  it("shows loading, then populated data with accessible controls and no N+1 request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([project]));
    vi.stubGlobal("fetch", fetchMock);
    renderProjects();
    expect(screen.getByText("Loading projects…")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: project.name })).toHaveAttribute("href", `/projects/${project.id}`);
    expect(screen.getByRole("navigation", { name: "Project pages" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/projects?limit=20&offset=0");
  });

  it("shows the empty state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));
    renderProjects();
    expect(await screen.findByText("No projects found.")).toBeInTheDocument();
  });

  it("shows a safe failure and retries manually without polling or persistence", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ detail: "secret" }, false)).mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    const getItem = vi.spyOn(Storage.prototype, "getItem");
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    renderProjects();
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No projects found.")).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 30));
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(document.body).not.toHaveTextContent("secret");
    expect(getItem).not.toHaveBeenCalled();
    expect(setItem).not.toHaveBeenCalled();
  });

  it("uses the real offset when advancing a full page", async () => {
    const page = Array.from({ length: 20 }, (_, index) => ({ ...project, id: `${index.toString(16).padStart(8, "0")}-1111-4111-8111-111111111111`, name: `Project ${index}` }));
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(page)).mockResolvedValueOnce(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);
    renderProjects();
    await userEvent.click(await screen.findByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toBe("/api/projects?limit=20&offset=20");
  });
});

describe("project creation", () => {
  it("validates, focuses name, and sends the exact trimmed body", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse(project, true, 201));
    vi.stubGlobal("fetch", fetchMock);
    renderProjects();
    const name = screen.getByLabelText("Name");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("Enter a project name.")).toBeInTheDocument();
    expect(name).toHaveFocus();
    await userEvent.type(name, "  Pure Axiom  ");
    await userEvent.type(screen.getByLabelText(/Description/), "  Interactive mathematics platform  ");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await screen.findByText("Created project page");
    expect(fetchMock.mock.calls[1][1]).toMatchObject({ method: "POST", body: JSON.stringify({ name: "Pure Axiom", description: "Interactive mathematics platform" }) });
  });

  it("prevents duplicate submission and disables controls", async () => {
    let resolveCreate!: (value: Response) => void;
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse([])).mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveCreate = resolve; }));
    vi.stubGlobal("fetch", fetchMock);
    renderProjects();
    await userEvent.type(screen.getByLabelText("Name"), "Project");
    await userEvent.dblClick(screen.getByRole("button", { name: "Create project" }));
    expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    resolveCreate(jsonResponse(project, true, 201));
  });

  it("keeps the form and user input after safe creation failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse({ detail: "private SQL" }, false)));
    renderProjects();
    await userEvent.type(screen.getByLabelText("Name"), "Keep me");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("The project could not be created. Try again.")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Keep me");
    expect(document.body).not.toHaveTextContent("private SQL");
  });

  it("cancels an in-flight creation on unmount", async () => {
    let createSignal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse([])).mockImplementationOnce((_url, init) => {
      createSignal = init?.signal;
      return new Promise(() => undefined);
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = renderProjects();
    await userEvent.type(screen.getByLabelText("Name"), "Project");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(createSignal?.aborted).toBe(false);
    view.unmount();
    expect(createSignal?.aborted).toBe(true);
  });
});

describe("project detail", () => {
  it("shows loading and every safe field", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(project)));
    renderDetail();
    expect(screen.getByText("Loading project…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: project.name })).toBeInTheDocument();
    for (const value of [project.id, project.description]) expect(screen.getByText(value)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to projects" })).toHaveAttribute("href", "/projects");
  });

  it("rejects a malformed route UUID without a request", () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock); renderDetail("bad-id");
    expect(screen.getByRole("heading", { name: "Invalid project address" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("distinguishes missing from safe errors and malformed payloads", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ detail: "project not found" }, false, 404));
    vi.stubGlobal("fetch", fetchMock); renderDetail();
    expect(await screen.findByRole("heading", { name: "Project not found" })).toBeInTheDocument();
    cleanup();
    fetchMock.mockResolvedValueOnce(jsonResponse({ ...project, internal: "secret" }));
    renderDetail();
    expect(await screen.findByRole("heading", { name: "Project unavailable" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("secret");
  });

  it("cancels the request on unmount", () => {
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => { signal = init?.signal; return new Promise(() => undefined); }));
    const view = renderDetail();
    expect(signal?.aborted).toBe(false);
    view.unmount();
    expect(signal?.aborted).toBe(true);
  });
});
