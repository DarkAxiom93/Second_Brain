import { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { getHealth, getReadiness } from "./api/client";

const navigation = [
  ["/", "Dashboard"],
  ["/projects", "Projects"],
  ["/sources", "Sources"],
  ["/proposals", "Proposals"],
  ["/memories", "Memories"],
  ["/search", "Search"],
  ["/answers", "Answers"],
  ["/settings", "Settings"],
] as const;

type ConnectionState = "loading" | "ready" | "error";

function Dashboard() {
  const [connection, setConnection] = useState<ConnectionState>("loading");
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setConnection("loading");
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setConnection("loading");
    Promise.all([getHealth(controller.signal), getReadiness(controller.signal)])
      .then(() => setConnection("ready"))
      .catch(() => {
        if (!controller.signal.aborted) {
          setConnection("error");
        }
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Local workspace</p>
        <h1>Dashboard</h1>
        <p>Confirm that the local API and database are available.</p>
      </header>
      <section className="status-card" aria-labelledby="connection-heading">
        <div>
          <h2 id="connection-heading">API connection</h2>
          <p className={`connection connection--${connection}`} aria-live="polite">
            <span aria-hidden="true" className="connection__dot" />
            {connection === "loading" && "Checking local services…"}
            {connection === "ready" && "Local services are ready"}
            {connection === "error" &&
              "Unable to confirm local services. Check that the API is running."}
          </p>
        </div>
        {connection === "ready" && (
          <dl className="service-grid">
            <div>
              <dt>API health</dt>
              <dd>Healthy</dd>
            </div>
            <div>
              <dt>Database readiness</dt>
              <dd>Ready</dd>
            </div>
          </dl>
        )}
        {connection === "error" && (
          <button type="button" onClick={retry}>
            Retry
          </button>
        )}
      </section>
    </>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <header className="page-header">
      <p className="eyebrow">Future screen</p>
      <h1>{title}</h1>
      <p>This area is reserved for a later user-interface checkpoint.</p>
    </header>
  );
}

function NotFound() {
  return (
    <header className="page-header">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The requested local page does not exist.</p>
    </header>
  );
}

export function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span aria-hidden="true" className="brand__mark">SB</span>
          <span>Second Brain</span>
        </div>
        <nav aria-label="Primary navigation">
          <ul>
            {navigation.map(([path, label]) => (
              <li key={path}>
                <NavLink end={path === "/"} to={path}>
                  {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <p className="sidebar__note">Local-first workspace</p>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          {navigation.slice(1).map(([path, label]) => (
            <Route key={path} path={path} element={<Placeholder title={label} />} />
          ))}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
