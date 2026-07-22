import { useCallback, useEffect, useState } from "react";
import { api, type DashboardStats, type UpdateRun, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

const ACTIONS = [
  { action: "sync_tracked", label: "同步指定 Workflow" },
  { action: "sync_current", label: "同步 Current Workflow" },
  { action: "fetch_comments", label: "获取 Final Mail 评论" },
  { action: "sync_sheets", label: "同步 Google Sheets" },
  { action: "pipeline", label: "运行完整 Pipeline" },
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
    const es = new EventSource(`/api/runs/${activeId}/events`);
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
              ? { ...prev, progress_pct: data.progress_pct ?? prev.progress_pct, current_stage: data.stage ?? prev.current_stage }
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
    <div>
      <h1 className="page-title">Dashboard</h1>
      <p className="page-sub">手动运行同步任务，查看系统状态与实时进度。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="grid stats" style={{ marginBottom: "1rem" }}>
        <div className="card">
          <div className="stat-value">{stats?.tracked_enabled ?? "—"}</div>
          <div className="stat-label">启用追踪</div>
        </div>
        <div className="card">
          <div className="stat-value">{stats?.current_count ?? "—"}</div>
          <div className="stat-label">进行中 Workflow</div>
        </div>
        <div className="card">
          <div className="stat-value">{stats?.pending_sheet_sync ?? "—"}</div>
          <div className="stat-label">待 Sheets 同步</div>
        </div>
        <div className="card">
          <div className="stat-value">{stats?.failed_sheet_sync ?? "—"}</div>
          <div className="stat-label">Sheets 失败</div>
        </div>
        <div className="card">
          <div className="stat-value">
            <span className={`badge ${stats?.aconex_configured ? "ok" : "warn"}`}>
              {stats?.aconex_configured ? "已配置" : "未配置"}
            </span>
          </div>
          <div className="stat-label">ACONEX</div>
        </div>
        <div className="card">
          <div className="stat-value">
            <span className={`badge ${stats?.sheets_configured ? "ok" : "warn"}`}>
              {stats?.sheets_configured ? "已配置" : "未配置"}
            </span>
          </div>
          <div className="stat-label">Google Sheets</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3>手动运行</h3>
        <div className="row">
          {ACTIONS.map((a) => (
            <button
              key={a.action}
              className="btn"
              disabled={busy !== null || active?.status === "running"}
              onClick={() => void runAction(a.action)}
            >
              {busy === a.action ? "启动中…" : a.label}
            </button>
          ))}
        </div>
      </div>

      {(active || stats?.last_run) && (
        <div className="card">
          <h3>运行进度 {active ? `#${active.id}` : stats?.last_run ? `#${stats.last_run.id}` : ""}</h3>
          {active && (
            <>
              <div className="row" style={{ marginBottom: "0.5rem" }}>
                <span className={`badge ${active.status === "running" ? "warn" : active.status === "success" ? "ok" : "err"}`}>
                  {active.status}
                </span>
                <span className="muted">{active.current_stage}</span>
                <span className="muted">{active.progress_pct?.toFixed?.(0) ?? 0}%</span>
              </div>
              <div className="progress" style={{ marginBottom: "0.75rem" }}>
                <span style={{ width: `${active.progress_pct || 0}%` }} />
              </div>
              <div className="muted" style={{ marginBottom: "0.5rem" }}>
                checked={active.checked_count} updated={active.updated_count} failed={active.failed_count} sheets=
                {active.sheet_synced_count}
              </div>
            </>
          )}
          <div className="log-box">
            {logs.length === 0 && <div className="muted">暂无日志</div>}
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
