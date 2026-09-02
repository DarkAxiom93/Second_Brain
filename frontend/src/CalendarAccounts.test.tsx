import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CalendarAccounts } from "./CalendarAccounts";

const id = "123e4567-e89b-42d3-a456-426614174000";
const reference = "sbcred:v1:12345678-1234-4123-8123-123456789abc";
const fingerprint = "a".repeat(64);
const account = (changes: Record<string, unknown> = {}) => ({ id, provider: "google_calendar", account_fingerprint: fingerprint, lifecycle: "enabled", configuration_revision: 1, scope: { kind: "unassigned", project_id: null }, calendar_ids: ["primary", "</li><script>alert(1)</script>?next=https://evil.example"], credential_status: "valid", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z", ...changes });
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.localStorage.clear(); window.sessionStorage.clear(); });

describe("Calendar account Settings UI", () => {
  it("configures exact safe metadata, clears credential fields, and uses no browser storage", async () => {
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn().mockResolvedValueOnce(response(account(), 201)).mockResolvedValueOnce(response([account()])); vi.stubGlobal("fetch", fetchMock); render(<CalendarAccounts />);
    await userEvent.type(screen.getByLabelText("Opaque credential reference"), reference); await userEvent.type(screen.getByLabelText("Safe account fingerprint"), fingerprint); await userEvent.type(screen.getByLabelText(/Exact calendar ID allowlist/), "primary"); await userEvent.click(screen.getByRole("button", { name: "Configure enabled Calendar account" }));
    expect(await screen.findByText(/Calendar account configured/)).toHaveFocus(); expect(screen.getByLabelText("Opaque credential reference")).toHaveValue(""); expect(screen.getByLabelText("Safe account fingerprint")).toHaveValue(""); expect(storage).not.toHaveBeenCalled();
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string); expect(body).toEqual({ credential_reference: reference, account_fingerprint: fingerprint, scope: { kind: "unassigned", project_id: null }, calendar_ids: ["primary"] });
  });

  it("renders hostile calendar IDs inertly with no provider-controlled links", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response([account()]))); render(<CalendarAccounts />); await userEvent.click(screen.getByRole("button", { name: "Load or refresh Calendar accounts" }));
    expect(await screen.findByText("</li><script>alert(1)</script>?next=https://evil.example")).toBeInTheDocument(); expect(document.querySelector("script")).toBeNull(); expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("requires explicit revoke confirmation and reports partial outcomes", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false); const fetchMock = vi.fn().mockResolvedValueOnce(response([account()])); vi.stubGlobal("fetch", fetchMock); render(<CalendarAccounts />); await userEvent.click(screen.getByRole("button", { name: "Load or refresh Calendar accounts" })); await screen.findByText(/Calendar account 123/);
    await userEvent.click(screen.getByRole("button", { name: "Revoke exact credential" })); expect(confirm).toHaveBeenCalledOnce(); expect(fetchMock).toHaveBeenCalledTimes(1);
    confirm.mockReturnValue(true); fetchMock.mockResolvedValueOnce(response({ account: account({ lifecycle: "revoked", configuration_revision: 2, credential_status: "revoked" }), provider_revoked: false, local_deleted: true })).mockResolvedValueOnce(response([account({ lifecycle: "revoked", configuration_revision: 2, credential_status: "revoked" })]));
    await userEvent.click(screen.getByRole("button", { name: "Revoke exact credential" })); expect(await screen.findByText(/Provider revocation: not completed; local deletion: completed/)).toHaveFocus(); expect(String(fetchMock.mock.calls[1][0])).toContain(`/calendar-accounts/${id}/revoke`);
  });

  it("allows revision-fenced edits only while disabled and refreshes stale conflicts", async () => {
    const disabled = account({ lifecycle: "disabled", configuration_revision: 2 }); const updated = account({ lifecycle: "disabled", configuration_revision: 3, calendar_ids: ["changed"] });
    const fetchMock = vi.fn().mockResolvedValueOnce(response([disabled])).mockResolvedValueOnce(response(updated)).mockResolvedValueOnce(response([updated])); vi.stubGlobal("fetch", fetchMock); render(<CalendarAccounts />); await userEvent.click(screen.getByRole("button", { name: "Load or refresh Calendar accounts" })); await userEvent.click(await screen.findByRole("button", { name: "Edit configuration" }));
    const input = screen.getByLabelText(/Exact calendar ID allowlist/); await userEvent.clear(input); await userEvent.type(input, "changed"); await userEvent.click(screen.getByRole("button", { name: "Save new configuration revision" })); await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const body = JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string); expect(body.expected_revision).toBe(2); expect(body.calendar_ids).toEqual(["changed"]);
  });

  it("has explicit labels, status announcements, and no token entry fields", () => {
    render(<CalendarAccounts />); expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite"); expect(screen.getByLabelText("Opaque credential reference")).toHaveAttribute("autocomplete", "off"); expect(screen.queryByLabelText(/access token|refresh token|id token|email|client secret/i)).not.toBeInTheDocument();
  });
});
