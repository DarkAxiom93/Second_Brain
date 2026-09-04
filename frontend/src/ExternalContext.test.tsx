import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CalendarContext, CalendarContextDetail, ConnectorScheduleControls, ExternalContext, ExternalContextDetail } from "./ExternalContext";

const account = { id: "123e4567-e89b-42d3-a456-426614174000", provider: "github", external_account_identity: "operator", scope: { kind: "unassigned", project_id: null }, repositories: ["owner/repo"], lifecycle: "enabled", validation_status: "valid", revision: 1, last_validated_at: null, created_at: "2026-08-28T10:00:00Z", updated_at: "2026-08-28T10:00:00Z" };
const hostile = "<script>alert(1)</script> [run](javascript:alert(2)) \u202e";
const item = { id: "223e4567-e89b-42d3-a456-426614174000", account_id: account.id, provider: "github", external_account_identity: "operator", scope: { kind: "unassigned", project_id: null }, external_resource_id: "github_repo:1", external_item_id: "github_issue:2", resource_type: "issue", application_revision: 1, provider_source_version: "2026-08-28T10:00:00Z:2", reconciliation_state: "current", title: hostile, content: { kind: "issue", number: 7, state: "open", body: hostile }, first_seen_at: "2026-08-28T10:00:00Z", revision_last_observed_at: "2026-08-28T10:00:00Z", created_sync_run_id: "323e4567-e89b-42d3-a456-426614174000", revision_last_observed_sync_run_id: "323e4567-e89b-42d3-a456-426614174000", confirmed_present_through: "2026-08-28T10:00:01Z", source_url: "https://github.com/owner/repo/issues/7", is_latest: true, trust: "external_untrusted" };
const response = (body: unknown) => ({ ok: true, status: 200, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;
const calendarItem = { id: "923e4567-e89b-42d3-a456-426614174000", occurrence_id: "a".repeat(64), provider: "google_calendar", source_label: "Calendar", scope: { kind: "unassigned", project_id: null }, application_revision: 1, event_type: "default", title: hostile, all_day: false, start_date: null, end_date: null, start_instant: "2026-09-04T07:00:00Z", end_instant: "2026-09-04T08:00:00Z", source_timezone: "Asia/Jerusalem", effective_state: "stale", last_evidence_at: "2026-09-05T10:00:00Z", trust: "external_untrusted" };

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("External Context", () => {
  it("loads scoped Calendar projections explicitly and renders hostile titles inertly", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(response([])).mockResolvedValueOnce(response({ items: [calendarItem], next_cursor: null }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><CalendarContext /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Calendar context" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Load Calendar context" }));
    expect(await screen.findByText(hostile)).toBeInTheDocument();
    expect(screen.getByText(/Calendar .* External \/ Untrusted .* stale/)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(screen.queryByRole("link", { name: /Google/i })).not.toBeInTheDocument();
    expect(String(fetchMock.mock.calls[1][0])).toContain("/calendar-events?scope=unassigned");
  });

  it("shows accessible Calendar detail with no action or provider link", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(calendarItem)));
    render(<MemoryRouter initialEntries={[`/external-context/calendar/${calendarItem.id}?scope=unassigned`]}><Routes><Route path="/external-context/calendar/:itemId" element={<CalendarContextDetail />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: hostile })).toBeInTheDocument();
    expect(screen.getByText(/no Agent, Automation, import, scheduling, or Calendar-write authority/)).toBeInTheDocument();
    expect(screen.getByText("stale")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Google/i })).not.toBeInTheDocument();
  });

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

  it("shows safe history and requires explicit pause, resume, and cancel actions", async () => {
    const base = { id: "723e4567-e89b-42d3-a456-426614174000", account_id: account.id, provider: "github", lifecycle: "enabled", revision: 1, schedule_revision: 0, schedule_kind: "daily", timezone_name: "UTC", local_time: "08:00:00", one_time_local_date: null, weekdays: [], interval_count: 1, nonexistent_time_policy: "first_valid_after_gap", ambiguous_time_policy: "earlier_fold", missed_run_policy: "run_once", next_occurrence_at: "2026-08-29T08:00:00Z", created_at: "2026-08-28T10:00:00Z", updated_at: "2026-08-28T10:00:00Z", cancelled_at: null };
    const occurrence = { id: "823e4567-e89b-42d3-a456-426614174000", schedule_id: base.id, account_id: account.id, provider: "github", connector_sync_run_id: "923e4567-e89b-42d3-a456-426614174000", scheduled_at: "2026-08-29T08:00:00Z", state: "failed", safe_error_code: "credential_missing", safe_disposition_code: "sync_failed", completed_at: "2026-08-29T08:00:01Z" };
    const paused = { ...base, lifecycle: "paused", revision: 2, next_occurrence_at: null };
    const resumed = { ...base, revision: 3 };
    const cancelled = { ...base, lifecycle: "cancelled", revision: 4, next_occurrence_at: null, cancelled_at: "2026-08-29T09:00:00Z" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response([account]))
      .mockResolvedValueOnce(response(base))
      .mockResolvedValueOnce(response([occurrence]))
      .mockResolvedValueOnce(response(paused))
      .mockResolvedValueOnce(response([occurrence]))
      .mockResolvedValueOnce(response(resumed))
      .mockResolvedValueOnce(response([occurrence]))
      .mockResolvedValueOnce(response(cancelled))
      .mockResolvedValueOnce(response([occurrence]));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><ConnectorScheduleControls /></MemoryRouter>);
    expect(await screen.findByText(/sync_failed/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(await screen.findByText("Schedule pause completed.")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Resume" }));
    expect(await screen.findByText("Schedule resume completed.")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Cancel future scheduling" }));
    expect(await screen.findByText("Schedule cancel completed.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel future scheduling" })).not.toBeInTheDocument();
    const actions = fetchMock.mock.calls.filter(call => (call[1] as RequestInit | undefined)?.method === "POST");
    expect(actions.map(call => String(call[0]).split("/").pop())).toEqual(["pause", "resume", "cancel"]);
    expect(actions.map(call => JSON.parse(String((call[1] as RequestInit).body)))).toEqual([
      { expected_revision: 1 }, { expected_revision: 2 }, { expected_revision: 3 },
    ]);
  });
});
