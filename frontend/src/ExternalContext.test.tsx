import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExternalContext } from "./ExternalContext";

const account = { id: "123e4567-e89b-42d3-a456-426614174000", provider: "github", external_account_identity: "operator", scope: { kind: "unassigned", project_id: null }, repositories: ["owner/repo"], lifecycle: "enabled", validation_status: "valid", revision: 1, last_validated_at: null, created_at: "2026-08-28T10:00:00Z", updated_at: "2026-08-28T10:00:00Z" };
const hostile = "<script>alert(1)</script> [run](javascript:alert(2)) \u202e";
const item = { id: "223e4567-e89b-42d3-a456-426614174000", account_id: account.id, provider: "github", external_account_identity: "operator", scope: { kind: "unassigned", project_id: null }, external_resource_id: "github_repo:1", external_item_id: "github_issue:2", resource_type: "issue", application_revision: 1, provider_source_version: "2026-08-28T10:00:00Z:2", reconciliation_state: "current", title: hostile, content: { kind: "issue", number: 7, state: "open", body: hostile }, first_seen_at: "2026-08-28T10:00:00Z", revision_last_observed_at: "2026-08-28T10:00:00Z", created_sync_run_id: "323e4567-e89b-42d3-a456-426614174000", revision_last_observed_sync_run_id: "323e4567-e89b-42d3-a456-426614174000", confirmed_present_through: "2026-08-28T10:00:01Z", source_url: "https://github.com/owner/repo/issues/7", is_latest: true, trust: "external_untrusted" };
const response = (body: unknown) => ({ ok: true, status: 200, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("External Context", () => {
  it("loads only on explicit action and renders hostile content as inert text", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response([account])).mockResolvedValueOnce(response([])).mockResolvedValueOnce(response({ items: [item], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><ExternalContext /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "External Context" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("button", { name: "Load external context" }));
    expect(await screen.findAllByText(hostile)).toHaveLength(2);
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(screen.getByText(/External \/ Untrusted · current/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
