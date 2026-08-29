import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorScheduleControls, ExternalContext, ExternalContextDetail } from "./ExternalContext";

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

  it("requires preview then exact confirmation and warns that no Memory is created", async () => {
    const preview = { account_id: account.id, external_item_row_id: item.id, external_resource_id: item.external_resource_id, external_item_id: item.external_item_id, application_revision: 1, trust: "external_untrusted", scope: item.scope, resource_type: "issue", title: hostile, normalized_text: `${hostile}\n\nIssue #7 (open)\n\n${hostile}`, provider_source_version: item.provider_source_version, content_hash: "a".repeat(64), canonical_source_url: item.source_url, confirmation_fingerprint: "b".repeat(64) };
    const result = { import_id: "423e4567-e89b-42d3-a456-426614174000", external_item_row_id: item.id, source_id: "523e4567-e89b-42d3-a456-426614174000", source_document_id: "623e4567-e89b-42d3-a456-426614174000", chunk_count: 1, import_status: "created" };
    const fetchMock = vi.fn().mockResolvedValueOnce(response(item)).mockResolvedValueOnce(response([item])).mockResolvedValueOnce(response(preview)).mockResolvedValueOnce(response(result));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter initialEntries={[`/external-context/${account.id}/${item.id}?scope=unassigned`]}><Routes><Route path="/external-context/:accountId/:itemId" element={<ExternalContextDetail />} /></Routes></MemoryRouter>);
    expect(await screen.findByText(/does not create Memory or proposals/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("button", { name: "Preview import" }));
    expect(await screen.findByRole("heading", { name: "Exact import preview" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await userEvent.click(screen.getByRole("button", { name: "Confirm exact import" }));
    expect(await screen.findByText(/Import created/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open resulting Source" })).toHaveAttribute("href", `/sources/${result.source_id}`);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("keeps connector scheduling draft-first with warning and explicit enable", async () => {
    const schedule = { id: "723e4567-e89b-42d3-a456-426614174000", account_id: account.id, provider: "github", lifecycle: "draft", revision: 0, schedule_revision: 0, schedule_kind: "daily", timezone_name: "UTC", local_time: "08:00:00", one_time_local_date: null, weekdays: [], interval_count: 1, nonexistent_time_policy: "first_valid_after_gap", ambiguous_time_policy: "earlier_fold", missed_run_policy: "skip", next_occurrence_at: null, created_at: "2026-08-28T10:00:00Z", updated_at: "2026-08-28T10:00:00Z", cancelled_at: null };
    const enabled = { ...schedule, lifecycle: "enabled", revision: 1, next_occurrence_at: "2026-08-29T08:00:00Z" };
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response([account]))
      .mockResolvedValueOnce(response(schedule))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response(enabled))
      .mockResolvedValueOnce(response([]));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><ConnectorScheduleControls /></MemoryRouter>);
    expect(await screen.findByText(/does not run an Agent and does not import content/)).toBeInTheDocument();
    const enable = await screen.findByRole("button", { name: "Enable explicitly" });
    expect(screen.getByText(/Status: draft/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
    await userEvent.click(enable);
    expect(await screen.findByText("Schedule enable completed.")).toBeInTheDocument();
    expect(fetchMock.mock.calls[3][1]).toMatchObject({ method: "POST" });
    expect(JSON.parse(String(fetchMock.mock.calls[3][1].body))).toEqual({ expected_revision: 0 });
    await new Promise(resolve => setTimeout(resolve, 30));
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(storage).not.toHaveBeenCalled();
  });
});
