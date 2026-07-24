import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUrl, type DashboardStats, type UpdateRun, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

const ACTIONS = [
  {
    action: "sync_tracked",
    label: "Tracked workflows",
    description: "Refresh only the workflow numbers in your tracking list.",
    icon: "sync",
  },
  {
    action: "sync_current",
    label: "Current workflows",
    description: "Discover and refresh workflows that are still in progress.",
    icon: "update",
  },
  {
    action: "fetch_comments",
    label: "Final Mail comments",
    description: "Fetch completion comments required by your feedback rules.",
    icon: "mail",
  },
  {
    action: "sync_sheets",
    label: "Google Sheets",
    description: "Write pending or failed rows without fetching ACONEX again.",
    icon: "table_chart",
  },
] as const;

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [active, setActive] = useState<UpdateRun | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const data = await api.get<DashboardStats>("/api/dashboard");
      setStats(data);
      setActive(data.active_run);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 8000);
    return () => clearInterval(t);
  }, [load]);

  const activeId = active?.id;
  const activeStatus = active?.status;

  useEffect(() => {
    if (!activeId || activeStatus !== "running") return;
    const es = new EventSource(apiUrl(`/api/runs/${activeId}/events`));
    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as {
          type: string;
          message?: string;
          level?: string;
          stage?: string;
          progress_pct?: number;
          status?: string;
          logs?: { level: string; stage: string; message: string }[];
        };
        if (data.type === "snapshot" && data.logs) {
          setLogs(data.logs.map((l) => `[${l.level}] ${l.stage}: ${l.message}`));
        }
        if (data.type === "log") {
          setLogs((prev) => [...prev, `[${data.level}] ${data.stage}: ${data.message}`]);
        }
        if (data.type === "progress") {
          setActive((prev) =>
            prev
              ? {
                  ...prev,
                  progress_pct: data.progress_pct ?? prev.progress_pct,
                  current_stage: data.stage ?? prev.current_stage,
                }
              : prev,
          );
        }
        if (data.type === "finished") {
          es.close();
          void load();
        }
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => es.close();
  }, [activeId, activeStatus, load]);

  async function runAction(action: string) {
    setBusy(action);
    setMsg("");
    setError("");
    try {
      const res = await api.post<{ run_id: number; message: string }>("/api/runs", { action });
      setMsg(`${res.message} (run #${res.run_id})`);
      setLogs([]);
      await load();
      const run = await api.get<UpdateRun>(`/api/runs/${res.run_id}`);
      setActive(run);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const isRunning = active?.status === "running";
  const setupComplete = Boolean(
    stats?.aconex_configured && stats?.sheets_configured && stats?.tracked_enabled,
  );
  const setupCount =
    Number(Boolean(stats?.aconex_configured)) +
    Number(Boolean(stats?.sheets_configured)) +
    Number(Boolean(stats?.tracked_enabled));

  return (
    <div className="page">
      <header className="page-header page-header-row">
        <div>
          <div className="eyebrow">Operations</div>
          <h1 className="page-title">Sync Center</h1>
          <p className="page-sub">
            Run the ACONEX → Google Sheets workflow and see exactly what needs your attention.
          </p>
        </div>
        <Link className="btn secondary" to="/guidance">
          <span className="material-symbols-outlined">explore</span>
          View guidance
        </Link>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      {!setupComplete && (
        <section className="setup-banner">
          <div className="setup-banner-icon">
            <span className="material-symbols-outlined">route</span>
          </div>
          <div className="setup-banner-copy">
            <div className="eyebrow">Before your first run · {setupCount}/3 ready</div>
            <h2>Finish the core setup</h2>
            <p>Connect both systems and choose at least one workflow. Guidance will take you through it.</p>
          </div>
          <Link className="btn" to="/guidance">
            Continue setup
            <span className="material-symbols-outlined">arrow_forward</span>
          </Link>
        </section>
      )}

      <section className="dashboard-grid">
        <div className="run-hero">
          <div className="run-hero-copy">
            <div className="run-hero-icon">
              <span className="material-symbols-outlined">{isRunning ? "sync" : "play_arrow"}</span>
            </div>
            <div>
              <div className="eyebrow">{isRunning ? "Pipeline running" : "Recommended action"}</div>
              <h2>{isRunning ? `Run #${active?.id} is in progress` : "Run the full pipeline"}</h2>
              <p>
                {isRunning
                  ? active?.current_stage || "Starting…"
                  : "Refresh ACONEX workflows, collect Final Mail comments, and sync changed rows to your sheet."}
              </p>
            </div>
          </div>
          {isRunning ? (
            <div className="run-hero-progress">
              <div className="progress">
                <span style={{ width: `${active?.progress_pct || 0}%` }} />
              </div>
              <strong>{active?.progress_pct?.toFixed?.(0) ?? 0}%</strong>
            </div>
          ) : (
            <button
              className="btn run-primary-button"
              disabled={busy !== null || !setupComplete}
              onClick={() => void runAction("pipeline")}
              title={!setupComplete ? "Complete the core setup before running" : undefined}
            >
              <span className="material-symbols-outlined">play_arrow</span>
              {busy === "pipeline" ? "Starting…" : "Run full pipeline"}
            </button>
          )}
        </div>

        <div className="health-card">
          <div className="card-header">
            <h3>
              <span className="material-symbols-outlined">health_and_safety</span>
              Connections
            </h3>
            <Link className="text-action" to="/guidance">Manage</Link>
          </div>
          <div className="connection-list">
            <Link to="/settings/aconex" className="connection-item">
              <span className={`status-dot ${stats?.aconex_configured ? "ok" : "warn"}`} />
              <span><strong>ACONEX</strong><small>{stats?.aconex_configured ? "Connected" : "Needs setup"}</small></span>
              <span className="material-symbols-outlined">chevron_right</span>
            </Link>
            <Link to="/settings/google-sheets" className="connection-item">
              <span className={`status-dot ${stats?.sheets_configured ? "ok" : "warn"}`} />
              <span><strong>Google Sheets</strong><small>{stats?.sheets_configured ? "Connected" : "Needs setup"}</small></span>
              <span className="material-symbols-outlined">chevron_right</span>
            </Link>
          </div>
        </div>
      </section>

      <div className="grid stats dashboard-stats">
        <Link to="/tracked" className="stat-card">
          <div className="stat-icon"><span className="material-symbols-outlined">track_changes</span></div>
          <div className="stat-value">{stats?.tracked_enabled ?? "—"}</div>
          <div className="stat-label">Workflows being tracked</div>
        </Link>
        <Link to="/workflows" className="stat-card">
          <div className="stat-icon"><span className="material-symbols-outlined">pending_actions</span></div>
          <div className="stat-value">{stats?.current_count ?? "—"}</div>
          <div className="stat-label">Workflows in progress</div>
        </Link>
        <Link to="/workflows" className="stat-card">
          <div className="stat-icon"><span className="material-symbols-outlined">cloud_upload</span></div>
          <div className="stat-value">{stats?.pending_sheet_sync ?? "—"}</div>
          <div className="stat-label">Rows waiting for Sheets</div>
        </Link>
        <Link to="/runs" className={`stat-card${stats?.failed_sheet_sync ? " has-error" : ""}`}>
          <div className="stat-icon"><span className="material-symbols-outlined">error</span></div>
          <div className="stat-value">{stats?.failed_sheet_sync ?? "—"}</div>
          <div className="stat-label">Sheet sync failures</div>
        </Link>
      </div>

      <details className="card advanced-actions">
        <summary>
          <span>
            <span className="material-symbols-outlined">tune</span>
            Run one pipeline stage
          </span>
          <span className="summary-help">For troubleshooting or targeted updates</span>
          <span className="material-symbols-outlined summary-chevron">expand_more</span>
        </summary>
        <div className="stage-action-grid">
          {ACTIONS.map((action) => (
            <button
              key={action.action}
              className="stage-action"
              disabled={busy !== null || isRunning}
              onClick={() => void runAction(action.action)}
            >
              <span className="stage-action-icon material-symbols-outlined">{action.icon}</span>
              <span>
                <strong>{busy === action.action ? "Starting…" : action.label}</strong>
                <small>{action.description}</small>
              </span>
              <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          ))}
        </div>
      </details>

      {(active || stats?.last_run) && (
        <div className="card stack">
          <div className="card-header">
            <h3>
              <span className="material-symbols-outlined">monitoring</span>
              Run Progress {active ? `#${active.id}` : stats?.last_run ? `#${stats.last_run.id}` : ""}
            </h3>
            {(active || stats?.last_run) && (
              <span
                className={`badge ${
                  (active || stats?.last_run)?.status === "running"
                    ? "warn"
                    : (active || stats?.last_run)?.status === "success"
                      ? "ok"
                      : "err"
                }`}
              >
                {(active || stats?.last_run)?.status}
              </span>
            )}
          </div>

          {active && (
            <>
              <div className="status-line">
                <div className="meta-pills">
                  <span className="muted">{active.current_stage || "—"}</span>
                  <span className="badge">{active.progress_pct?.toFixed?.(0) ?? 0}%</span>
                </div>
                <div className="muted mono">
                  checked={active.checked_count} · updated={active.updated_count} · failed=
                  {active.failed_count} · sheets={active.sheet_synced_count}
                </div>
              </div>
              <div className="progress">
                <span style={{ width: `${active.progress_pct || 0}%` }} />
              </div>
            </>
          )}

          <div className="log-box">
            {logs.length === 0 && <div className="muted">No logs yet</div>}
            {logs.map((line, i) => (
              <div key={i} className={line.includes("[ERROR]") ? "ERROR" : ""}>
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
