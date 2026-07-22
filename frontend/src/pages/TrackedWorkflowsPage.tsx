import { useEffect, useState } from "react";
import { api, type TrackedWorkflow, ApiError } from "../api/client";
import { Alert } from "../components/Alert";
import { Switch } from "../components/Switch";

export function TrackedWorkflowsPage() {
  const [items, setItems] = useState<TrackedWorkflow[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      setItems(await api.get<TrackedWorkflow[]>("/api/tracked-workflows"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function batchAdd() {
    setError("");
    setMsg("");
    try {
      const res = await api.post<{ created: number; skipped: number; total: number }>(
        "/api/tracked-workflows/batch",
        { text, enabled: true },
      );
      setMsg(`Done: created ${res.created}, skipped ${res.skipped}, parsed ${res.total}`);
      setText("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function toggle(item: TrackedWorkflow, enabled: boolean) {
    try {
      await api.patch(`/api/tracked-workflows/${item.id}`, { enabled });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/api/tracked-workflows/${id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Tracked Workflows</h1>
        <p className="page-sub">
          Add, enable/pause, or delete workflow numbers. Batch input and ranges (e.g. 800-850) are supported.
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack">
        <h3>
          <span className="material-symbols-outlined">playlist_add</span>
          Batch Add
        </h3>
        <label>
          Workflow numbers
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Examples:\n800-850\nWF-900, WF-901\n910"}
          />
        </label>
        <div className="actions">
          <button className="btn" onClick={() => void batchAdd()}>
            <span className="material-symbols-outlined">add</span>
            Batch Add
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">list_alt</span>
            Tracking List
          </h3>
          <span className="badge">{items.length}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th className="center">Enabled</th>
                <th>Status</th>
                <th>Notes</th>
                <th className="center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="mono">{item.workflow_number}</td>
                  <td className="center">
                    <div className="row center">
                      <Switch
                        checked={item.enabled}
                        onChange={(v) => void toggle(item, v)}
                        label={item.enabled ? "On" : "Off"}
                      />
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${item.enabled ? "ok" : "warn"}`}>
                      {item.enabled ? "Enabled" : "Paused"}
                    </span>
                  </td>
                  <td>{item.notes || "—"}</td>
                  <td className="center">
                    <button className="btn sm danger" onClick={() => void remove(item.id)}>
                      <span className="material-symbols-outlined">delete</span>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-cell">
                    No tracked items yet. You can also use &quot;Sync Current&quot; on the Dashboard to discover
                    workflows.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
