import { useCallback, useEffect, useRef, useState } from "react";

import {
  getHealth,
  getOperationsDiagnostics,
  getOperationsMaintenanceAudit,
  getReadiness,
  executeProjectImport,
  exportProject,
  listProjects,
  validateProjectImport,
  type ProjectImportPlan,
  type ProjectRead,
  type OperationsDiagnostics,
  type OperationsMaintenanceAudit,
} from "./api/client";
import { ConnectorAccounts } from "./ConnectorAccounts";
import { CalendarAccounts } from "./CalendarAccounts";

type LoadState = "loading" | "ready" | "error";
const labels: Record<string, string> = {
  active_expiration_due: "Active Memories due for expiration",
  active_future_expiration: "Active Memories with future expiration",
  active_missing_embedding: "Active Memories missing embeddings",
  active_stale_embedding: "Active Memories with stale or incompatible embeddings",
  expired_missing_expires_at: "Expired Memories missing an expiration timestamp",
  non_active_with_embedding: "Non-active Memories retaining embeddings",
};

export function Settings() {
  const [attempt, setAttempt] = useState(0);
  const [active, setActive] = useState(false);
  const [health, setHealth] = useState<LoadState>("loading");
  const [diagnosticsState, setDiagnosticsState] = useState<LoadState>("loading");
  const [maintenanceState, setMaintenanceState] = useState<LoadState>("loading");
  const [diagnostics, setDiagnostics] = useState<OperationsDiagnostics | null>(null);
  const [maintenance, setMaintenance] = useState<OperationsMaintenanceAudit | null>(null);
  const activeRef = useRef(false);
  const summaryRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLHeadingElement>(null);
  const initial = useRef(true);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [projectOffset, setProjectOffset] = useState(0);
  const [selectedProject, setSelectedProject] = useState("");
  const [exportState, setExportState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [plan, setPlan] = useState<ProjectImportPlan | null>(null);
  const [importState, setImportState] = useState<"idle" | "validating" | "executing" | "success" | "error">("idle");
  const [confirmationId, setConfirmationId] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const operationController = useRef<AbortController | null>(null);
  const selectedFileRef = useRef<File | null>(null);
  const planRef = useRef<HTMLHeadingElement>(null);
  const importErrorRef = useRef<HTMLParagraphElement>(null);
  const successRef = useRef<HTMLHeadingElement>(null);
  const projectPageSize = 20;
  const maxBundleSize = 128 * 1024 * 1024;

  const loadProjects = async (offset: number) => {
    try { const page = await listProjects(projectPageSize, offset); setProjects(page); setProjectOffset(offset); if (!page.some(p => p.id === selectedProject)) setSelectedProject(""); }
    catch { setProjects([]); setExportState("error"); }
  };
  const startExport = async () => {
    if (!selectedProject || exportState === "loading") return;
    const controller = new AbortController(); operationController.current = controller; setExportState("loading");
    try {
      const download = await exportProject(selectedProject, controller.signal);
      const url = URL.createObjectURL(download.blob); try { const anchor = document.createElement("a"); anchor.href = url; anchor.download = download.filename; anchor.click(); } finally { URL.revokeObjectURL(url); } setExportState("success");
    } catch { if (!controller.signal.aborted) setExportState("error"); }
    finally { operationController.current = null; }
  };
  const chooseFile = (selected: File | null) => {
    operationController.current?.abort(); selectedFileRef.current = selected; setFile(selected); setPlan(null); setConfirmationId(""); setConfirmed(false); setImportState("idle");
    setFileError(!selected ? "Select one .sbexport file." : !selected.name.toLowerCase().endsWith(".sbexport") ? "Select a file with the .sbexport extension." : selected.size === 0 ? "The selected bundle is empty." : selected.size > maxBundleSize ? "The selected bundle exceeds the 128 MiB limit." : "");
  };
  const validateBundle = async () => {
    if (!file || fileError || importState === "validating") return;
    const activeFile = file; const controller = new AbortController(); operationController.current = controller; setPlan(null); setImportState("validating");
    try { const value = await validateProjectImport(activeFile, controller.signal); if (selectedFileRef.current === activeFile) { setPlan(value); setImportState("idle"); requestAnimationFrame(() => planRef.current?.focus()); } }
    catch { if (!controller.signal.aborted) { setImportState("error"); requestAnimationFrame(() => importErrorRef.current?.focus()); } }
    finally { operationController.current = null; }
  };
  const executeBundle = async () => {
    if (!file || !plan?.importable || confirmationId !== plan.project_id || !confirmed || importState === "executing") return;
    const activeFile = file; const controller = new AbortController(); operationController.current = controller; setImportState("executing");
    try { await executeProjectImport(activeFile, plan.project_id, plan.bundle_sha256, controller.signal); setPlan(null); setConfirmed(false); setConfirmationId(""); setImportState("success"); requestAnimationFrame(() => successRef.current?.focus()); }
    catch { if (!controller.signal.aborted) { setPlan(null); setImportState("error"); requestAnimationFrame(() => importErrorRef.current?.focus()); } }
    finally { operationController.current = null; }
  };

  const refresh = useCallback(() => {
    if (activeRef.current) return;
    activeRef.current = true;
    setActive(true);
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    activeRef.current = true;
    setActive(true);
    setHealth("loading");
    setDiagnosticsState("loading");
    setMaintenanceState("loading");
    Promise.allSettled([
      Promise.all([getHealth(controller.signal), getReadiness(controller.signal)]),
      getOperationsDiagnostics(controller.signal),
      getOperationsMaintenanceAudit(controller.signal),
    ]).then(([services, diagnosticResult, maintenanceResult]) => {
      if (controller.signal.aborted) return;
      setHealth(services.status === "fulfilled" ? "ready" : "error");
      if (diagnosticResult.status === "fulfilled") {
        setDiagnostics(diagnosticResult.value); setDiagnosticsState("ready");
      } else { setDiagnostics(null); setDiagnosticsState("error"); }
      if (maintenanceResult.status === "fulfilled") {
        setMaintenance(maintenanceResult.value); setMaintenanceState("ready");
      } else { setMaintenance(null); setMaintenanceState("error"); }
      setActive(false);
      activeRef.current = false;
      if (!initial.current) {
        window.requestAnimationFrame(() => {
          if (services.status === "rejected" && diagnosticResult.status === "rejected" && maintenanceResult.status === "rejected") errorRef.current?.focus();
          else summaryRef.current?.focus();
        });
      }
      initial.current = false;
    });
    return () => controller.abort();
  }, [attempt]);

  const activeCount = maintenance?.counts_by_status.active ?? 0;
  const missing = maintenance?.findings.find((item) => item.finding_id === "active_missing_embedding")?.count ?? 0;
  const stale = maintenance?.findings.find((item) => item.finding_id === "active_stale_embedding")?.count ?? 0;
  const embeddedCurrent = Math.max(0, activeCount - missing - stale);
  const allFailed = health === "error" && diagnosticsState === "error" && maintenanceState === "error";

  return <>
    <header className="page-header settings-header">
      <div><p className="eyebrow">Local operations</p><h1>Settings</h1><p>Read-only health, diagnostics, and maintenance guidance for this workspace.</p></div>
      <button type="button" onClick={refresh} disabled={active}>{active ? "Refreshingâ€¦" : "Refresh"}</button>
    </header>
    <section className="status-card settings-summary" aria-labelledby="operations-summary-heading" aria-live="polite">
      <h2 id="operations-summary-heading" ref={summaryRef} tabIndex={-1}>Dashboard summary</h2>
      {active && <p>Loading operational statusâ€¦</p>}
      {!active && allFailed && <><h3 ref={errorRef} tabIndex={-1}>Operational status unavailable</h3><p>Safe operational information could not be loaded. Refresh after confirming the local API and database are running.</p></>}
      {!active && !allFailed && <p>{diagnostics?.diagnostics_status === "unhealthy" || health === "error" ? "Unhealthy: one or more operational checks failed." : diagnostics?.warning_count ? "Warning: services responded, but diagnostics need attention." : "Healthy: available operational checks passed."}</p>}
    </section>
    <section className="panel" aria-labelledby="health-heading"><h2 id="health-heading">Health and readiness</h2>
      {health === "loading" && <p>Checking API health and database readinessâ€¦</p>}
      {health === "ready" && <dl className="service-grid"><div><dt>API health</dt><dd>Passed â€” Healthy</dd></div><div><dt>Database readiness</dt><dd>Passed â€” Ready</dd></div></dl>}
      {health === "error" && <p>Failed â€” API health or database readiness could not be confirmed.</p>}
    </section>
    <section className="panel operations-panel" aria-labelledby="diagnostics-heading"><h2 id="diagnostics-heading">System diagnostics</h2>
      {diagnosticsState === "loading" && <p>Loading safe diagnostic checksâ€¦</p>}
      {diagnosticsState === "error" && <p>Diagnostics could not be loaded. No server details were displayed.</p>}
      {diagnosticsState === "ready" && diagnostics && <><p><strong>{diagnostics.diagnostics_status === "healthy" ? "Healthy" : "Unhealthy"}</strong> â€” {diagnostics.warning_count} warnings, {diagnostics.failure_count} failures. Captured {new Date(diagnostics.captured_at).toLocaleString()}.</p><ul className="operations-list">{diagnostics.checks.map((check) => <li key={`${check.category}-${check.check_id}`}><span className={`status-label status-label--${check.status}`}>{check.status === "passed" ? "Passed" : check.status === "warning" ? "Warning" : "Failed"}</span><div><strong>{check.check_id.replaceAll("_", " ")}</strong><small>{check.category}</small><p>{check.message}</p></div></li>)}</ul><h3>Informational aggregates</h3><dl className="count-grid">{Object.entries(diagnostics.aggregate_counts).map(([name, count]) => <div key={name}><dt>{name}</dt><dd>{count}</dd></div>)}</dl></>}
    </section>
    <section className="panel operations-panel" aria-labelledby="maintenance-heading"><h2 id="maintenance-heading">Maintenance audit</h2>
      <p>Findings are advisory. This dashboard never repairs or changes data.</p>
      {maintenanceState === "loading" && <p>Loading maintenance aggregatesâ€¦</p>}
      {maintenanceState === "error" && <p>Maintenance aggregates could not be loaded.</p>}
      {maintenanceState === "ready" && maintenance && <><dl className="count-grid"><div><dt>Total Memories</dt><dd>{maintenance.total_memories}</dd></div><div><dt>Active Memories</dt><dd>{activeCount}</dd></div><div><dt>Project assigned</dt><dd>{maintenance.project_assigned_memories}</dd></div><div><dt>Unassigned</dt><dd>{maintenance.unassigned_memories}</dd></div></dl>{maintenance.findings.every((item) => item.count === 0) ? <p>No actionable maintenance findings.</p> : <ul className="finding-list">{maintenance.findings.map((item) => <li key={item.finding_id}><span>{labels[item.finding_id] ?? item.finding_id.replaceAll("_", " ")}</span><strong>{item.count}</strong></li>)}</ul>}</>}
    </section>
    <section className="panel" aria-labelledby="embedding-heading"><h2 id="embedding-heading">Embedding coverage</h2>
      {maintenanceState === "loading" && <p>Loading embedding coverageâ€¦</p>}
      {maintenanceState === "error" && <p>Embedding coverage could not be loaded.</p>}
      {maintenanceState === "ready" && <dl className="count-grid"><div><dt>Active Memories</dt><dd>{activeCount}</dd></div><div><dt>Current embeddings</dt><dd>{embeddedCurrent}</dd></div><div><dt>Missing embeddings</dt><dd>{missing}</dd></div><div><dt>Stale or incompatible</dt><dd>{stale}</dd></div></dl>}
    </section>
    <ConnectorAccounts />
    <CalendarAccounts />
    <section className="panel operations-panel" aria-labelledby="export-heading"><h2 id="export-heading">Project Export</h2><p>Download one private, unencrypted Project bundle. Store it securely.</p>
      {projects.length === 0 ? <button type="button" onClick={() => void loadProjects(0)}>Load Projects</button> : <><label htmlFor="export-project">Project</label><select id="export-project" value={selectedProject} onChange={e => setSelectedProject(e.target.value)}><option value="">Select a Project</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><div className="actions"><button type="button" disabled={!selectedProject || exportState === "loading"} onClick={() => void startExport()}>{exportState === "loading" ? "Exporting…" : "Export selected Project"}</button><button type="button" disabled={projectOffset === 0} onClick={() => void loadProjects(Math.max(0, projectOffset - projectPageSize))}>Previous Projects</button><button type="button" disabled={projects.length < projectPageSize} onClick={() => void loadProjects(projectOffset + projectPageSize)}>Next Projects</button>{exportState === "loading" && <button type="button" onClick={() => operationController.current?.abort()}>Cancel Export</button>}</div></>}
      <p aria-live="polite">{exportState === "success" ? "Export download started." : exportState === "error" ? "The Project export could not be downloaded safely." : ""}</p>
    </section>
    <section className="panel operations-panel" aria-labelledby="validation-heading"><h2 id="validation-heading">Import Validation</h2><p>Validation reads the complete bundle but does not write application data.</p><label htmlFor="import-file">Project export bundle (.sbexport, maximum 128 MiB)</label><input id="import-file" type="file" accept=".sbexport" onChange={e => chooseFile(e.currentTarget.files?.item(0) ?? null)} />{fileError && <p className="error-text" role="alert">{fileError}</p>}<div className="actions"><button type="button" disabled={!file || !!fileError || importState === "validating" || importState === "executing"} onClick={() => void validateBundle()}>{importState === "validating" ? "Validating…" : "Validate bundle"}</button>{importState === "validating" && <button type="button" onClick={() => operationController.current?.abort()}>Cancel Validation</button>}</div>
      {importState === "error" && <p ref={importErrorRef} tabIndex={-1} role="alert">The bundle is malformed, stale, conflicting, or could not be processed safely. Validate it again before execution.</p>}
      {plan && <div className="import-plan" aria-live="polite"><h3 ref={planRef} tabIndex={-1}>Import plan: {plan.importable ? "Importable" : "Valid but conflicting"}</h3><dl className="count-grid"><div><dt>Format</dt><dd>{plan.format_name} v{plan.format_version}</dd></div><div><dt>Project</dt><dd>{plan.project_name}</dd></div><div><dt>Project ID</dt><dd>{plan.project_id}</dd></div><div><dt>Source revision</dt><dd>{plan.source_alembic_revision}</dd></div><div><dt>Bundle SHA-256</dt><dd>{plan.bundle_sha256}</dd></div><div><dt>Warnings / conflicts</dt><dd>{plan.warning_count} / {plan.conflict_count}</dd></div></dl><h4>Entity counts</h4><dl className="count-grid">{Object.entries(plan.entity_counts).map(([name, count]) => <div key={name}><dt>{name}</dt><dd>{count}</dd></div>)}</dl>{plan.conflicts.length > 0 && <><h4>Conflicts</h4><ul>{plan.conflicts.map(message => <li key={message}>{message}</li>)}</ul></>}</div>}
    </section>
    <section className="panel operations-panel" aria-labelledby="execution-heading"><h2 id="execution-heading">Controlled Import Execution</h2><p><strong>Irreversible action:</strong> imports only a completely conflict-free bundle. There is no merge, overwrite, remap, repair, or partial import.</p><label htmlFor="confirm-project">Type the exact manifest Project UUID</label><input id="confirm-project" value={confirmationId} onChange={e => setConfirmationId(e.target.value)} disabled={!plan?.importable} /><label className="checkbox-row"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} disabled={!plan?.importable} /> I explicitly confirm this irreversible import.</label><button type="button" className="danger" disabled={!file || !plan?.importable || confirmationId !== plan?.project_id || !confirmed || importState === "executing"} onClick={() => void executeBundle()}>{importState === "executing" ? "Importing…" : "Execute controlled import"}</button>{importState === "success" && <h3 ref={successRef} tabIndex={-1} aria-live="polite">Project imported successfully. The validation plan has been invalidated.</h3>}</section>
    <section className="panel" aria-labelledby="limitations-heading"><h2 id="limitations-heading">Current limitations</h2><p>GitHub refresh is explicit and manual; there is no polling, scheduling, automatic retry, external write, import, or automatic repair.</p><p>Version 1 bundles are not encrypted. Export and import are direct local streamed operations with temporary-file cleanup and a strict no-conflict policy.</p></section>
  </>;
}
