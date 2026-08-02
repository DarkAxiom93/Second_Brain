import { useCallback, useEffect, useRef, useState } from "react";

import {
  getHealth,
  getOperationsDiagnostics,
  getOperationsMaintenanceAudit,
  getReadiness,
  type OperationsDiagnostics,
  type OperationsMaintenanceAudit,
} from "./api/client";

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
    <section className="panel" aria-labelledby="limitations-heading"><h2 id="limitations-heading">Current limitations</h2><p>Refresh is manual; there is no polling, automatic retry, provider call, migration, or automatic repair.</p><p>Export and controlled Import remain available through the existing PowerShell commands. Their user-interface controls are deferred to Checkpoint 51.</p></section>
  </>;
}
