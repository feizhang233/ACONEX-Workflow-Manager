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
import { Switch } from "../components/Switch";

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
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Workflow Data</h1>
        <p className="page-sub">
          Browse synced workflows, step status, and change history. Total: {total}.
        </p>
      </header>

      <Alert type="error">{error}</Alert>

      <div className="card">
        <div className="toolbar">
          <label>
            Search
            <input
              placeholder="Search by number or title"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </label>
          <div className="switch-group" style={{ paddingTop: "1.35rem" }}>
            <Switch checked={currentOnly} onChange={setCurrentOnly} label="In progress only" />
          </div>
          <div style={{ paddingTop: "1.35rem" }}>
            <button className="btn secondary" onClick={() => void load()}>
              <span className="material-symbols-outlined">search</span>
              Search
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">account_tree</span>
            Workflow List
          </h3>
          <span className="badge">{items.length}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Status</th>
                <th className="center">Steps</th>
                <th>Checked</th>
                <th className="center">Actions</th>
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
                  <td className="center">{w.steps?.length ?? 0}</td>
                  <td className="muted mono">{w.last_checked_at || "—"}</td>
                  <td className="center">
                    <button className="btn sm secondary" onClick={() => void open(w)}>
                      Details
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty-cell">
                    No data yet. Run a sync from the Dashboard first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="stack">
          <div className="card stack">
            <div className="card-header">
              <h3>
                <span className="material-symbols-outlined">description</span>
                {selected.workflow_number} — {selected.workflow_title}
              </h3>
              <button className="btn sm secondary" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
            <p className="muted" style={{ margin: 0 }}>
              status={selected.review_status} · outcome={selected.review_outcome} · source=
              {selected.source}
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
            <h3>
              <span className="material-symbols-outlined">history</span>
              Change History
            </h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Summary</th>
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
                      <td colSpan={3} className="empty-cell">
                        No history
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
