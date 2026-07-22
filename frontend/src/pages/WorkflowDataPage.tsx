import { useEffect, useState } from "react";
import {
  api,
  type Paginated,
  type Workflow,
  type WorkflowHistory,
  type WorkflowStep,
  ApiError,
} from "../api/client";
import { Alert } from "../components/Alert";

export function WorkflowDataPage() {
  const [items, setItems] = useState<Workflow[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [currentOnly, setCurrentOnly] = useState(false);
  const [selected, setSelected] = useState<Workflow | null>(null);
  const [history, setHistory] = useState<WorkflowHistory[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      const params = new URLSearchParams({
        page: "1",
        page_size: "100",
        current_only: String(currentOnly),
      });
      if (q.trim()) params.set("q", q.trim());
      const data = await api.get<Paginated<Workflow>>(`/api/workflows?${params}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when filter changes
  }, [currentOnly]);

  async function open(wf: Workflow) {
    try {
      const detail = await api.get<Workflow>(`/api/workflows/${encodeURIComponent(wf.workflow_number)}`);
      setSelected(detail);
      const hist = await api.get<WorkflowHistory[]>(
        `/api/workflows/${encodeURIComponent(wf.workflow_number)}/history`,
      );
      setHistory(hist);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div>
      <h1 className="page-title">Workflow 数据</h1>
      <p className="page-sub">查看已同步的 Workflow、Step 状态与变更历史。共 {total} 条。</p>
      <Alert type="error">{error}</Alert>

      <div className="card row" style={{ marginBottom: "1rem" }}>
        <input
          placeholder="搜索编号或标题"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <label style={{ flexDirection: "row", alignItems: "center" }}>
          <input type="checkbox" checked={currentOnly} onChange={(e) => setCurrentOnly(e.target.checked)} />
          仅进行中
        </label>
        <button className="btn secondary" onClick={() => void load()}>
          查询
        </button>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Status</th>
                <th>Steps</th>
                <th>Checked</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((w) => (
                <tr key={w.id}>
                  <td className="mono">{w.workflow_number}</td>
                  <td>{w.workflow_title}</td>
                  <td>
                    <span className={`badge ${w.is_completed ? "ok" : "warn"}`}>
                      {w.review_status || (w.is_completed ? "Completed" : "Open")}
                    </span>
                  </td>
                  <td>{w.steps?.length ?? 0}</td>
                  <td className="muted mono">{w.last_checked_at || "—"}</td>
                  <td>
                    <button className="btn sm secondary" onClick={() => void open(w)}>
                      详情
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    暂无数据，请先在 Dashboard 运行同步。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="stack">
          <div className="card">
            <h3>
              {selected.workflow_number} — {selected.workflow_title}
            </h3>
            <p className="muted">
              status={selected.review_status} outcome={selected.review_outcome} source={selected.source}
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Participant</th>
                    <th>Due</th>
                    <th>Completed</th>
                    <th>Overdue</th>
                    <th>Sheet</th>
                    <th>Comment</th>
                  </tr>
                </thead>
                <tbody>
                  {(selected.steps || []).map((s: WorkflowStep) => (
                    <tr key={s.id}>
                      <td>
                        {s.step_index != null ? `#${s.step_index} ` : ""}
                        {s.step_name}
                      </td>
                      <td>{s.step_status}</td>
                      <td>{s.step_outcome}</td>
                      <td>{s.participant}</td>
                      <td className="mono">{s.date_due}</td>
                      <td className="mono">{s.date_completed}</td>
                      <td>{s.overdue}</td>
                      <td>
                        <span
                          className={`badge ${
                            s.sheet_sync_status === "synced"
                              ? "ok"
                              : s.sheet_sync_status === "failed"
                                ? "err"
                                : "warn"
                          }`}
                        >
                          {s.sheet_sync_status}
                        </span>
                      </td>
                      <td style={{ maxWidth: 220 }}>{s.final_mail_comment || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <h3>变更历史</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>摘要</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td className="mono">{h.checked_at}</td>
                      <td>{h.change_type}</td>
                      <td>
                        {h.change_summary}
                        {h.step_name ? ` (${h.step_name})` : ""}
                      </td>
                    </tr>
                  ))}
                  {history.length === 0 && (
                    <tr>
                      <td colSpan={3} className="muted">
                        无历史
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
