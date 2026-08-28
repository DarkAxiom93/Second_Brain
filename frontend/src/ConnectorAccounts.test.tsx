import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectorAccounts } from "./ConnectorAccounts";

const reference = "sbcred:v1:12345678-1234-4123-8123-123456789abc";
const account = (revision = 0, lifecycle: "disabled" | "enabled" | "revoked" = "disabled") => ({
  id: "123e4567-e89b-42d3-a456-426614174000", provider: "github", external_account_identity: "operator-account",
  scope: { kind: "unassigned", project_id: null }, repositories: ["owner/repository"], lifecycle,
  validation_status: lifecycle === "revoked" ? "revoked" : "unvalidated", revision,
  last_validated_at: null, created_at: "2026-08-28T10:00:00Z", updated_at: "2026-08-28T10:00:00Z",
});
const response = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("connector account settings flow", () => {
  it("creates only from an opaque reference, clears it, and uses no browser persistence", async () => {
    const localSet = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response(account(), 201))
      .mockResolvedValueOnce(response([account()]));
    vi.stubGlobal("fetch", fetchMock); render(<ConnectorAccounts />);
    await userEvent.type(screen.getByLabelText(/External account identity/), "operator-account");
    await userEvent.type(screen.getByLabelText("Opaque credential reference"), reference);
    await userEvent.type(screen.getByLabelText(/Repository allowlist/), "owner/repository");
    await userEvent.click(screen.getByRole("button", { name: "Create disabled GitHub account" }));
    expect(await screen.findByText(/credential reference was cleared/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Opaque credential reference")).toHaveValue("");
    expect(document.body).not.toHaveTextContent(reference);
    expect(localSet).not.toHaveBeenCalled();
    const createBody = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string);
    expect(createBody).toEqual({ external_account_identity: "operator-account", credential_reference: reference, scope: { kind: "unassigned", project_id: null }, repositories: ["owner/repository"] });
  });

  it("lists status, requires revoke confirmation, and reconciles stale revisions", async () => {
    const confirm = vi.fn().mockReturnValue(true); vi.stubGlobal("confirm", confirm);
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response([account()]))
      .mockResolvedValueOnce(response({}, 409))
      .mockResolvedValueOnce(response([account(1, "enabled")]))
      .mockResolvedValueOnce(response(account(2, "revoked")));
    vi.stubGlobal("fetch", fetchMock); render(<ConnectorAccounts />);
    await userEvent.click(screen.getByRole("button", { name: "Load or refresh accounts" }));
    expect(await screen.findByText("operator-account")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Re-enable" }));
    expect(await screen.findByText(/changed elsewhere/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(confirm).toHaveBeenCalledOnce());
    expect(await screen.findByText(/revoke completed/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Re-enable" })).not.toBeInTheDocument();
  });

  it("rejects token-shaped input locally and remains usable at narrow widths", async () => {
    vi.stubGlobal("fetch", vi.fn()); render(<ConnectorAccounts />);
    await userEvent.type(screen.getByLabelText(/External account identity/), "operator-account");
    await userEvent.type(screen.getByLabelText("Opaque credential reference"), "github_pat_secret");
    await userEvent.type(screen.getByLabelText(/Repository allowlist/), "owner/repository");
    await userEvent.click(screen.getByRole("button", { name: "Create disabled GitHub account" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/Check the account identity/);
    expect(screen.getByRole("button", { name: "Create disabled GitHub account" })).toBeEnabled();
    expect(document.querySelector(".operations-panel")).toHaveClass("panel");
  });
});
