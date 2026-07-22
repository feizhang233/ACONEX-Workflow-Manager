import { useCallback, useEffect, useState } from "react";
import { api, apiUrl, type DashboardStats, type UpdateRun, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

const ACTIONS = [
  { action: "sync_tracked", label: "Sync Tracked Workflows", icon: "sync" },
  { action: "sync_current", label: "Sync Current Workflows", icon: "update" },
  { action: "fetch_comments", label: "Fetch Final Mail Comments", icon: "mail" },
  { action: "sync_sheets", label: "Sync Google Sheets", icon: "table_chart" },
  { action: "pipeline", label: "Run Full Pipeline", icon: "play_arrow" },
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

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-sub">Run sync jobs manually and monitor system status with live progress.</p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="grid stats">
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">track_changes</span>
          </div>
          <div className="stat-value">{stats?.tracked_enabled ?? "—"}</div>
          <div className="stat-label">Enabled Tracking</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">pending_actions</span>
          </div>
          <div className="stat-value">{stats?.current_count ?? "—"}</div>
          <div className="stat-label">In-progress Workflows</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">cloud_upload</span>
          </div>
          <div className="stat-value">{stats?.pending_sheet_sync ?? "—"}</div>
          <div className="stat-label">Pending Sheet Sync</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">error</span>
          </div>
          <div className="stat-value">{stats?.failed_sheet_sync ?? "—"}</div>
          <div className="stat-label">Sheet Sync Failures</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">vpn_key</span>
          </div>
          <div className="stat-value">
            <span className={`badge ${stats?.aconex_configured ? "ok" : "warn"}`}>
              {stats?.aconex_configured ? "Configured" : "Not set"}
            </span>
          </div>
          <div className="stat-label">ACONEX</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon">
            <span className="material-symbols-outlined">table_chart</span>
          </div>
          <div className="stat-value">
            <span className={`badge ${stats?.sheets_configured ? "ok" : "warn"}`}>
              {stats?.sheets_configured ? "Configured" : "Not set"}
            </span>
          </div>
          <div className="stat-label">Google Sheets</div>
        </div>
      </div>

      <div className="card">
        <h3>
          <span className="material-symbols-outlined">bolt</span>
          Manual Run
        </h3>
        <div className="action-grid">
          {ACTIONS.map((a) => (
            <button
              key={a.action}
              className={`btn ${a.action === "pipeline" ? "" : "secondary"}`}
              disabled={busy !== null || active?.status === "running"}
              onClick={() => void runAction(a.action)}
            >
              <span className="material-symbols-outlined">{a.icon}</span>
              {busy === a.action ? "Starting…" : a.label}
            </button>
          ))}
        </div>
      </div>

      {(active || stats?.last_run) && (
        <div className="card stack">
          <div className="card-header">
            <h3>
              <span className="material-symbols-outlined">monitoring</span>
              Run Progress {active ? `#${active.id}` : stats?.last_run ? `#${stats.last_run.id}` : ""}
            </h3>
            {active && (
              <span
                className={`badge ${
                  active.status === "running" ? "warn" : active.status === "success" ? "ok" : "err"
                }`}
              >
                {active.status}
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
