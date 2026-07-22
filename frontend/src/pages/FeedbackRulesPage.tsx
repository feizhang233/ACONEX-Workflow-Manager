import { useEffect, useState } from "react";
import { api, type FeedbackRule, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

const STATUS_OPTS = ["Pending", "A", "B", "C", "Completed", "Terminated"];
const TRIGGER_OPTS = ["always", "data_changed", "pending_to_final", "overdue", "workflow_completed"];
const FIELD_OPTS = [
  "workflow_number",
  "workflow_title",
  "step_index",
  "step_name",
  "step_status",
  "step_outcome",
  "participant",
  "date_due",
  "date_completed",
  "overdue",
  "final_mail_comment",
  "review_status",
  "review_outcome",
];

type Form = {
  name: string;
  enabled: boolean;
  step_selector: string;
  step_indexes: string;
  step_names: string;
  output_fields: string[];
  status_filter: string[];
  triggers: string[];
  fetch_final_mail: boolean;
  priority: number;
  notes: string;
};

const blank: Form = {
  name: "",
  enabled: true,
  step_selector: "all",
  step_indexes: "",
  step_names: "",
  output_fields: [...FIELD_OPTS],
  status_filter: [...STATUS_OPTS],
  triggers: ["always", "data_changed", "pending_to_final"],
  fetch_final_mail: true,
  priority: 100,
  notes: "",
};

export function FeedbackRulesPage() {
  const [rules, setRules] = useState<FeedbackRule[]>([]);
  const [form, setForm] = useState<Form>(blank);
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      setRules(await api.get<FeedbackRule[]>("/api/feedback-rules"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function toggleList(key: "output_fields" | "status_filter" | "triggers", value: string) {
    setForm((f) => {
      const arr = f[key];
      return {
        ...f,
        [key]: arr.includes(value) ? arr.filter((x) => x !== value) : [...arr, value],
      };
    });
  }

  function startEdit(rule: FeedbackRule) {
    setEditId(rule.id);
    setForm({
      name: rule.name,
      enabled: rule.enabled,
      step_selector: rule.step_selector,
      step_indexes: (rule.step_indexes || []).join(","),
      step_names: (rule.step_names || []).join(","),
      output_fields: rule.output_fields || [],
      status_filter: rule.status_filter || [],
      triggers: rule.triggers || [],
      fetch_final_mail: rule.fetch_final_mail,
      priority: rule.priority,
      notes: rule.notes || "",
    });
  }

  async function save() {
    setError("");
    setMsg("");
    if (!form.name.trim()) {
      setError("请填写规则名称");
      return;
    }
    const payload = {
      name: form.name.trim(),
      enabled: form.enabled,
      step_selector: form.step_selector,
      step_indexes: form.step_indexes
        .split(/[,\s]+/)
        .filter(Boolean)
        .map((n) => Number(n))
        .filter((n) => !Number.isNaN(n)),
      step_names: form.step_names
        .split(/[,\n]+/)
        .map((s) => s.trim())
        .filter(Boolean),
      output_fields: form.output_fields,
      status_filter: form.status_filter,
      triggers: form.triggers,
      fetch_final_mail: form.fetch_final_mail,
      priority: form.priority,
      notes: form.notes,
    };
    try {
      if (editId) {
        await api.put(`/api/feedback-rules/${editId}`, payload);
        setMsg("规则已更新");
      } else {
        await api.post("/api/feedback-rules", payload);
        setMsg("规则已创建");
      }
      setForm(blank);
      setEditId(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/api/feedback-rules/${id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div>
      <h1 className="page-title">Step / 反馈规则</h1>
      <p className="page-sub">自定义哪些 Step、字段、状态与触发条件参与同步和 Final Mail 抓取（不写死 Step 2）。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack" style={{ marginBottom: "1rem" }}>
        <h3>{editId ? `编辑规则 #${editId}` : "新建规则"}</h3>
        <div className="form-grid">
          <label>
            名称
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label>
            优先级（越小越优先）
            <input
              type="number"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
            />
          </label>
          <label>
            Step 选择方式
            <select
              value={form.step_selector}
              onChange={(e) => setForm({ ...form, step_selector: e.target.value })}
            >
              <option value="all">全部 Step</option>
              <option value="by_index">按序号</option>
              <option value="by_name">按名称</option>
            </select>
          </label>
          <label>
            Step 序号（逗号分隔）
            <input
              value={form.step_indexes}
              onChange={(e) => setForm({ ...form, step_indexes: e.target.value })}
              placeholder="例如 1,2"
              disabled={form.step_selector !== "by_index"}
            />
          </label>
          <label>
            Step 名称（逗号分隔）
            <input
              value={form.step_names}
              onChange={(e) => setForm({ ...form, step_names: e.target.value })}
              placeholder="例如 Step 2, GDS Review"
              disabled={form.step_selector !== "by_name"}
            />
          </label>
        </div>

        <div>
          <div className="muted">输出字段</div>
          <div className="checkbox-row">
            {FIELD_OPTS.map((f) => (
              <label key={f}>
                <input
                  type="checkbox"
                  checked={form.output_fields.includes(f)}
                  onChange={() => toggleList("output_fields", f)}
                />
                {f}
              </label>
            ))}
          </div>
        </div>

        <div>
          <div className="muted">状态过滤</div>
          <div className="checkbox-row">
            {STATUS_OPTS.map((s) => (
              <label key={s}>
                <input
                  type="checkbox"
                  checked={form.status_filter.includes(s)}
                  onChange={() => toggleList("status_filter", s)}
                />
                {s}
              </label>
            ))}
          </div>
        </div>

        <div>
          <div className="muted">触发条件</div>
          <div className="checkbox-row">
            {TRIGGER_OPTS.map((t) => (
              <label key={t}>
                <input
                  type="checkbox"
                  checked={form.triggers.includes(t)}
                  onChange={() => toggleList("triggers", t)}
                />
                {t}
              </label>
            ))}
          </div>
        </div>

        <div className="checkbox-row">
          <label>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            启用
          </label>
          <label>
            <input
              type="checkbox"
              checked={form.fetch_final_mail}
              onChange={(e) => setForm({ ...form, fetch_final_mail: e.target.checked })}
            />
            抓取 Final Mail 评论
          </label>
        </div>

        <label>
          备注
          <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </label>

        <div className="row">
          <button className="btn" onClick={() => void save()}>
            {editId ? "更新" : "创建"}
          </button>
          {editId && (
            <button
              className="btn secondary"
              onClick={() => {
                setEditId(null);
                setForm(blank);
              }}
            >
              取消编辑
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <h3>现有规则</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>Step</th>
                <th>触发</th>
                <th>Mail</th>
                <th>状态</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.name} <span className="muted">P{r.priority}</span>
                  </td>
                  <td className="mono">
                    {r.step_selector}
                    {r.step_selector === "by_index" ? ` [${r.step_indexes.join(",")}]` : ""}
                    {r.step_selector === "by_name" ? ` [${r.step_names.join(",")}]` : ""}
                  </td>
                  <td>{r.triggers.join(", ")}</td>
                  <td>{r.fetch_final_mail ? "是" : "否"}</td>
                  <td>
                    <span className={`badge ${r.enabled ? "ok" : "warn"}`}>{r.enabled ? "启用" : "停用"}</span>
                  </td>
                  <td className="row">
                    <button className="btn sm secondary" onClick={() => startEdit(r)}>
                      编辑
                    </button>
                    <button className="btn sm danger" onClick={() => void remove(r.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
