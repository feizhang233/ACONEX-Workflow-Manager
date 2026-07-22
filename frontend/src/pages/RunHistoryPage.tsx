import { useEffect, useState } from "react";
import { api, type Paginated, type UpdateRun, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

export function RunHistoryPage() {
  const [items, setItems] = useState<UpdateRun[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<UpdateRun | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      const data = await api.get<Paginated<UpdateRun>>("/api/runs?page=1&page_size=50");
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 10000);
    return () => clearInterval(t);
  }, []);

  async function openRun(id: number) {
    try {
      setSelected(await api.get<UpdateRun>(`/api/runs/${id}`));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function retry(id: number) {
    setError("");
    setMsg("");
    try {
      const res = await api.post<{ run_id: number }>(`/api/runs/${id}/retry`);
      setMsg(`Retry started as run #${res.run_id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Run History</h1>
        <p className="page-sub">
          Review stage logs, counters, and errors for each job. Failed runs can be retried. Total: {total}.
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">history</span>
            Runs
          </h3>
          <span className="badge">{items.length}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Command</th>
                <th>Status</th>
                <th>Started</th>
                <th>Finished</th>
                <th>Counts</th>
                <th className="center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>
                    {r.command}
                    <div className="muted">{r.triggered_by}</div>
                  </td>
                  <td>
                    <span
                      className={`badge ${
                        r.status === "success" ? "ok" : r.status === "running" ? "warn" : "err"
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="mono">{r.started_at}</td>
                  <td className="mono">{r.finished_at || "—"}</td>
                  <td className="muted mono">
                    c={r.checked_count} u={r.updated_count} f={r.failed_count} s={r.sheet_synced_count}
                  </td>
                  <td className="center">
                    <div className="row center">
                      <button className="btn sm secondary" onClick={() => void openRun(r.id)}>
                        Details
                      </button>
                      {r.status === "failed" && (
                        <button className="btn sm" onClick={() => void retry(r.id)}>
                          Retry
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    No runs yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="card stack">
          <div className="card-header">
            <h3>
              <span className="material-symbols-outlined">terminal</span>
              Run #{selected.id} — {selected.command}
            </h3>
            <button className="btn sm secondary" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
          {selected.error_message && <Alert type="error">{selected.error_message}</Alert>}
          <div className="progress">
            <span style={{ width: `${selected.progress_pct || 0}%` }} />
          </div>
          <div className="log-box">
            {(selected.logs || []).map((l) => (
              <div key={l.id} className={l.level}>
                [{l.timestamp}] [{l.level}] {l.stage}: {l.message}
              </div>
            ))}
            {(selected.logs || []).length === 0 && <div>No logs</div>}
          </div>
        </div>
      )}
    </div>
  );
}
