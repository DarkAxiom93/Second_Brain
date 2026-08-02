import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";

const response = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 503, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;
const diagnostics = (status: "passed" | "warning" | "failed" = "passed") => ({
  diagnostics_status: status === "failed" ? "unhealthy" : "healthy",
  captured_at: "2026-08-02T10:00:00Z",
  warning_count: status === "warning" ? 1 : 0,
  failure_count: status === "failed" ? 1 : 0,
  checks: [{ check_id: "current_revision", category: "alembic", status, message: "Safe migration status." }],
  aggregate_counts: { Memories: 4, Projects: 1 },
});
const maintenance = (missing = 1) => ({
  captured_at: "2026-08-02T10:00:00Z", total_memories: 4,
  project_assigned_memories: 3, unassigned_memories: 1,
  counts_by_status: { active: 3, archived: 0, expired: 1, invalid: 0, superseded: 0 },
  findings: [
    { finding_id: "active_expiration_due", count: 0 },
    { finding_id: "active_future_expiration", count: 0 },
    { finding_id: "active_missing_embedding", count: missing },
    { finding_id: "active_stale_embedding", count: 1 },
    { finding_id: "expired_missing_expires_at", count: 0 },
    { finding_id: "non_active_with_embedding", count: 0 },
  ],
});

function successfulFetch(status: "passed" | "warning" | "failed" = "passed", missing = 1) {
  return vi.fn()
    .mockResolvedValueOnce(response({ status: "ok" }))
    .mockResolvedValueOnce(response({ status: "ready" }))
    .mockResolvedValueOnce(response(diagnostics(status)))
    .mockResolvedValueOnce(response(maintenance(missing)));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("settings operations dashboard", () => {
  it("renders loading then health, diagnostics, maintenance, and embedding coverage without polling", async () => {
    const fetchMock = successfulFetch(); vi.stubGlobal("fetch", fetchMock); render(<Settings />);
    expect(screen.getByText(/Loading operational status/)).toBeInTheDocument();
    expect(await screen.findByText(/Healthy: available operational checks passed/)).toBeInTheDocument();
    expect(screen.getByText("Passed â€” Healthy")).toBeInTheDocument();
    expect(screen.getByText("Safe migration status.")).toBeInTheDocument();
    expect(screen.getByText("Active Memories missing embeddings")).toBeInTheDocument();
    expect(screen.getByText("Current embeddings").nextElementSibling).toHaveTextContent("1");
    await new Promise((resolve) => window.setTimeout(resolve, 20));
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it.each([
    ["warning", /Warning: services responded/],
    ["failed", /Unhealthy: one or more/],
  ] as const)("renders explicit %s status text", async (status, expected) => {
    vi.stubGlobal("fetch", successfulFetch(status)); render(<Settings />);
    expect(await screen.findByText(expected)).toBeInTheDocument();
    expect(screen.getByText(status === "warning" ? "Warning" : "Failed")).toBeInTheDocument();
  });

  it("renders empty maintenance and independent safe failures", async () => {
    const empty = maintenance(0); empty.findings.forEach((item) => { item.count = 0; });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ status: "ok" })).mockResolvedValueOnce(response({ status: "ready" }))
      .mockResolvedValueOnce(response({}, false)).mockResolvedValueOnce(response(empty));
    vi.stubGlobal("fetch", fetchMock); render(<Settings />);
    expect(await screen.findByText(/Diagnostics could not be loaded/)).toBeInTheDocument();
    expect(screen.getByText("No actionable maintenance findings.")).toBeInTheDocument();
  });

  it("refreshes once, prevents duplicates, and focuses the refreshed summary", async () => {
    const fetchMock = successfulFetch();
    for (const value of [response({ status: "ok" }), response({ status: "ready" }), response(diagnostics()), response(maintenance())]) fetchMock.mockResolvedValueOnce(value);
    vi.stubGlobal("fetch", fetchMock); render(<Settings />);
    const button = await screen.findByRole("button", { name: "Refresh" });
    await userEvent.click(button);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(8));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard summary" })).toHaveFocus());
  });

  it("rejects malformed or sensitive payloads and renders no raw data", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ status: "ok" })).mockResolvedValueOnce(response({ status: "ready" }))
      .mockResolvedValueOnce(response({ ...diagnostics(), database_url: "postgresql://admin:secret@host/db" }))
      .mockResolvedValueOnce(response({ ...maintenance(), vectors: [[1, 2]], content: "private evidence" }));
    vi.stubGlobal("fetch", fetchMock); render(<Settings />);
    expect(await screen.findByText(/Diagnostics could not be loaded/)).toBeInTheDocument();
    expect(screen.getByText(/Maintenance aggregates could not be loaded/)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("secret");
    expect(document.body).not.toHaveTextContent("private evidence");
    expect(document.body).not.toHaveTextContent("postgresql");
  });

  it("cancels obsolete requests on unmount and exposes no mutation controls", () => {
    const signals: AbortSignal[] = [];
    vi.stubGlobal("fetch", vi.fn((_url, init) => { signals.push((init as RequestInit).signal as AbortSignal); return new Promise(() => undefined); }));
    const view = render(<Settings />); view.unmount();
    expect(signals).toHaveLength(4); expect(signals.every((signal) => signal.aborted)).toBe(true);
    for (const name of [/repair/i, /migrate/i, /generate/i, /delete/i, /export/i, /import/i]) expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
  });
});
