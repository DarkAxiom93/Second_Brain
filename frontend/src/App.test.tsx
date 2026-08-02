import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

function renderAt(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("application shell", () => {
  it("renders the shell and every navigation link", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    renderAt();
    expect(screen.getByText("Second Brain")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    for (const name of [
      "Dashboard", "Projects", "Sources", "Proposals", "Memories",
      "Search", "Answers", "Settings",
    ]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
  });

  it.each([
    ["/memories", "Memories"],
    ["/search", "Search"],
    ["/answers", "Answers"],
    ["/settings", "Settings"],
  ])("renders the %s placeholder without a backend request", (path, title) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderAt(path);
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText(/later user-interface checkpoint/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("opens the functional proposal queue", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock); renderAt("/proposals");
    expect(await screen.findByText("No proposals match these filters.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/memory-proposals?review_status=pending&limit=20&offset=0", expect.anything());
  });

  it("opens the functional Sources screen from navigation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse([])));
    renderAt();
    await userEvent.click(screen.getByRole("link", { name: "Sources" }));
    expect(await screen.findByRole("heading", { name: "Create a source" })).toBeInTheDocument();
    expect(screen.queryByText(/later user-interface checkpoint/i)).not.toBeInTheDocument();
  });

  it("renders Not Found for an unknown route without contacting the backend", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/not-a-real-page");
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("dashboard", () => {
  it("shows loading and requests health and readiness", () => {
    const fetchMock = vi.fn<(input: RequestInfo | URL) => Promise<Response>>(
      () => new Promise(() => undefined),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderAt();
    expect(screen.getByText("Checking local services…")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/health",
      "/api/ready",
    ]);
  });

  it("renders successful responses safely and does not poll", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }))
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));
    vi.stubGlobal("fetch", fetchMock);
    renderAt();
    expect(await screen.findByText("Local services are ready")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    await new Promise((resolve) => window.setTimeout(resolve, 30));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows a generic safe failure without sensitive response details", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ detail: "postgresql://admin:secret@internal-db/db" }, false),
      )
      .mockRejectedValueOnce(new Error("internal host 10.0.0.9"));
    vi.stubGlobal("fetch", fetchMock);
    renderAt();
    expect(await screen.findByText(/unable to confirm local services/i)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("secret");
    expect(document.body).not.toHaveTextContent("10.0.0.9");
    expect(document.body).not.toHaveTextContent("postgresql");
  });

  it("performs new requests when Retry is activated", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({}, false))
      .mockResolvedValueOnce(jsonResponse({}, false))
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }))
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));
    vi.stubGlobal("fetch", fetchMock);
    renderAt();
    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Local services are ready")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("rejects a malformed success response as a safe client error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ status: "ok", internalHost: "private.example" }),
      )
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));
    vi.stubGlobal("fetch", fetchMock);
    renderAt();
    await waitFor(() =>
      expect(screen.getByText(/unable to confirm local services/i)).toBeInTheDocument(),
    );
    expect(document.body).not.toHaveTextContent("private.example");
  });
});
