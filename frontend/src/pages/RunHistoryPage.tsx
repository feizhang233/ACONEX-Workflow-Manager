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
      setMsg(`已启动重试 run #${res.run_id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div>
      <h1 className="page-title">运行历史</h1>
      <p className="page-sub">查看每次任务的阶段日志、计数与错误，可重试失败任务。共 {total} 条。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>命令</th>
                <th>状态</th>
                <th>开始</th>
                <th>结束</th>
                <th>计数</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
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
                  <td className="muted">
                    c={r.checked_count} u={r.updated_count} f={r.failed_count} s={r.sheet_synced_count}
                  </td>
                  <td className="row">
                    <button className="btn sm secondary" onClick={() => void openRun(r.id)}>
                      详情
                    </button>
                    {r.status === "failed" && (
                      <button className="btn sm" onClick={() => void retry(r.id)}>
                        重试
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="card">
          <h3>
            Run #{selected.id} — {selected.command}
          </h3>
          {selected.error_message && <Alert type="error">{selected.error_message}</Alert>}
          <div className="progress" style={{ marginBottom: "0.75rem" }}>
            <span style={{ width: `${selected.progress_pct || 0}%` }} />
          </div>
          <div className="log-box">
            {(selected.logs || []).map((l) => (
              <div key={l.id} className={l.level}>
                [{l.timestamp}] [{l.level}] {l.stage}: {l.message}
              </div>
            ))}
            {(selected.logs || []).length === 0 && <div>无日志</div>}
          </div>
        </div>
      )}
    </div>
  );
}
