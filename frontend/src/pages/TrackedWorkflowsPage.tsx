import { useEffect, useState } from "react";
import { api, type TrackedWorkflow, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

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
      setMsg(`添加完成：新建 ${res.created}，跳过 ${res.skipped}，共解析 ${res.total}`);
      setText("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function toggle(item: TrackedWorkflow) {
    try {
      await api.patch(`/api/tracked-workflows/${item.id}`, { enabled: !item.enabled });
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
    <div>
      <h1 className="page-title">Workflow 追踪</h1>
      <p className="page-sub">添加、启用/暂停、删除 Workflow Number。支持批量与范围（如 800-850）。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack" style={{ marginBottom: "1rem" }}>
        <label>
          批量输入编号
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"示例：\n800-850\nWF-900, WF-901\n910"}
          />
        </label>
        <div className="row">
          <button className="btn" onClick={() => void batchAdd()}>
            批量添加
          </button>
        </div>
      </div>

      <div className="card">
        <h3>追踪列表（{items.length}）</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Number</th>
                <th>状态</th>
                <th>备注</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td className="mono">{item.workflow_number}</td>
                  <td>
                    <span className={`badge ${item.enabled ? "ok" : "warn"}`}>
                      {item.enabled ? "启用" : "暂停"}
                    </span>
                  </td>
                  <td>{item.notes || "—"}</td>
                  <td className="row">
                    <button className="btn sm secondary" onClick={() => void toggle(item)}>
                      {item.enabled ? "暂停" : "启用"}
                    </button>
                    <button className="btn sm danger" onClick={() => void remove(item.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    暂无追踪项。也可在 Dashboard 使用「同步 Current」自动发现。
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
