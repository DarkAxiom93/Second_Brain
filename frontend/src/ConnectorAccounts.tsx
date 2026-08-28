import { useRef, useState } from "react";

import { ApiConflictError, connectorLifecycle, createConnectorAccount, listConnectorAccounts, listProjects, type ConnectorAccount, type ProjectRead } from "./api/client";

const REFERENCE = /^sbcred:v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const REPOSITORY = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\/[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/;

export function ConnectorAccounts() {
  const [accounts, setAccounts] = useState<ConnectorAccount[]>([]);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [identity, setIdentity] = useState("");
  const [credentialReference, setCredentialReference] = useState("");
  const [scope, setScope] = useState("unassigned");
  const [repositories, setRepositories] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const statusRef = useRef<HTMLParagraphElement>(null);

  const announce = (value: string) => { setMessage(value); requestAnimationFrame(() => statusRef.current?.focus()); };
  const refresh = async () => {
    setBusy(true);
    try { setAccounts(await listConnectorAccounts()); announce("Connector accounts refreshed."); }
    catch { announce("Connector accounts could not be loaded safely."); }
    finally { setBusy(false); }
  };
  const loadProjects = async () => {
    setBusy(true);
    try { setProjects(await listProjects(100, 0)); announce("Projects loaded for connector scope selection."); }
    catch { announce("Projects could not be loaded safely."); }
    finally { setBusy(false); }
  };
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    const repoList = repositories.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    if (!identity.trim() || !REFERENCE.test(credentialReference) || repoList.length < 1 || repoList.length > 32 || repoList.some(x => !REPOSITORY.test(x)) || (scope !== "unassigned" && !projects.some(x => x.id === scope))) {
      announce("Check the account identity, opaque credential reference, exact scope, and 1 to 32 owner/repository entries."); return;
    }
    setBusy(true);
    try {
      await createConnectorAccount({ external_account_identity: identity.trim(), credential_reference: credentialReference, scope: scope === "unassigned" ? { kind: "unassigned", project_id: null } : { kind: "project", project_id: scope }, repositories: repoList });
      setCredentialReference(""); setIdentity(""); setRepositories(""); setScope("unassigned");
      setAccounts(await listConnectorAccounts()); announce("GitHub account metadata created disabled and unvalidated. The credential reference was cleared.");
    } catch { setCredentialReference(""); announce("Connector account metadata could not be created safely. The credential reference was cleared."); }
    finally { setBusy(false); }
  };
  const mutate = async (account: ConnectorAccount, action: "disable" | "re-enable" | "revoke") => {
    if (action === "revoke" && !window.confirm("Revoke this connector account? Revocation is terminal and prevents future use.")) return;
    setBusy(true);
    try {
      const updated = await connectorLifecycle(account.id, action, account.revision);
      setAccounts(values => values.map(value => value.id === updated.id ? updated : value)); announce(`Connector account ${action} completed.`);
    } catch (error) {
      if (error instanceof ApiConflictError) { try { setAccounts(await listConnectorAccounts()); announce("The account changed elsewhere. Current state was refreshed; review it before retrying."); } catch { announce("The account changed elsewhere and refresh failed safely."); } }
      else announce("The connector lifecycle action failed safely.");
    } finally { setBusy(false); }
  };

  return <section className="panel operations-panel" aria-labelledby="connector-heading">
    <h2 id="connector-heading">GitHub connector accounts</h2>
    <p>Metadata only. Install the credential itself with <code>scripts/manage-credential.ps1</code>, then paste only its opaque <code>sbcred:v1:&lt;UUIDv4&gt;</code> reference here. Never enter a GitHub token, password, or private client credential.</p>
    <div className="actions"><button type="button" onClick={() => void refresh()} disabled={busy}>Load or refresh accounts</button><button type="button" onClick={() => void loadProjects()} disabled={busy}>Load scope Projects</button></div>
    <p ref={statusRef} tabIndex={-1} role="status" aria-live="polite">{message}</p>
    <form onSubmit={event => void create(event)} autoComplete="off">
      <label htmlFor="connector-identity">External account identity <span>(operator supplied, unvalidated)</span></label>
      <input id="connector-identity" value={identity} maxLength={255} onChange={event => setIdentity(event.target.value)} autoComplete="off" />
      <label htmlFor="connector-reference">Opaque credential reference</label>
      <input id="connector-reference" value={credentialReference} onChange={event => setCredentialReference(event.target.value)} placeholder="sbcred:v1:00000000-0000-4000-8000-000000000000" autoComplete="off" spellCheck={false} />
      <label htmlFor="connector-scope">Project scope</label>
      <select id="connector-scope" value={scope} onChange={event => setScope(event.target.value)}><option value="unassigned">Unassigned (not unrestricted)</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
      <label htmlFor="connector-repositories">Repository allowlist <span>(one canonical owner/repository per line, maximum 32)</span></label>
      <textarea id="connector-repositories" value={repositories} onChange={event => setRepositories(event.target.value)} />
      <button type="submit" disabled={busy}>Create disabled GitHub account</button>
    </form>
    {accounts.length === 0 ? <p>No connector accounts loaded.</p> : <ul className="connector-list">{accounts.map(account => <li key={account.id}><h3>{account.external_account_identity}</h3><p><strong>{account.lifecycle}</strong> · {account.validation_status} · revision {account.revision}</p><p>Scope: {account.scope.kind === "unassigned" ? "Unassigned" : projects.find(project => project.id === account.scope.project_id)?.name ?? account.scope.project_id}</p><p>Repositories: {account.repositories.join(", ")}</p><div className="actions">{account.lifecycle === "enabled" && <button type="button" disabled={busy} onClick={() => void mutate(account, "disable")}>Disable</button>}{account.lifecycle === "disabled" && <button type="button" disabled={busy} onClick={() => void mutate(account, "re-enable")}>Re-enable</button>}{account.lifecycle !== "revoked" && <button type="button" className="danger" disabled={busy} onClick={() => void mutate(account, "revoke")}>Revoke</button>}</div></li>)}</ul>}
  </section>;
}
