import { useEffect, useState } from "react";
import { api, type FeedbackRule, ApiError } from "../api/client";
import { Alert } from "../components/Alert";
import { Switch } from "../components/Switch";

/** Stored API values remain short codes; UI shows full labels. */
const STATUS_OPTS: { value: string; label: string }[] = [
  { value: "Pending", label: "Pending" },
  { value: "A", label: "A — Approved" },
  { value: "B", label: "B — Approved with Comments" },
  { value: "C", label: "C — Rejected" },
  { value: "Completed", label: "Completed" },
  { value: "Terminated", label: "Terminated" },
];

const TRIGGER_OPTS: { value: string; label: string }[] = [
  { value: "always", label: "Always" },
  { value: "data_changed", label: "Data changed" },
  { value: "pending_to_final", label: "Pending → Final" },
  { value: "overdue", label: "Overdue" },
  { value: "workflow_completed", label: "Workflow completed" },
];

const FIELD_OPTS: { value: string; label: string }[] = [
  { value: "workflow_number", label: "Workflow number" },
  { value: "workflow_title", label: "Workflow title" },
  { value: "step_index", label: "Step index" },
  { value: "step_name", label: "Step name" },
  { value: "step_status", label: "Step status" },
  { value: "step_outcome", label: "Step outcome" },
  { value: "participant", label: "Participant" },
  { value: "date_due", label: "Date due" },
  { value: "date_completed", label: "Date completed" },
  { value: "overdue", label: "Overdue" },
  { value: "final_mail_comment", label: "Final mail comment" },
  { value: "review_status", label: "Review status" },
  { value: "review_outcome", label: "Review outcome" },
];

const DEFAULT_STATUS = STATUS_OPTS.map((s) => s.value);
const DEFAULT_FIELDS = FIELD_OPTS.map((f) => f.value);
const DEFAULT_TRIGGERS = ["always", "data_changed", "pending_to_final"];

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
  output_fields: [...DEFAULT_FIELDS],
  status_filter: [...DEFAULT_STATUS],
  triggers: [...DEFAULT_TRIGGERS],
  fetch_final_mail: true,
  priority: 100,
  notes: "",
};

function statusLabel(code: string): string {
  return STATUS_OPTS.find((s) => s.value === code)?.label ?? code;
}

function triggerLabel(code: string): string {
  return TRIGGER_OPTS.find((t) => t.value === code)?.label ?? code;
}

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

  function selectAll(key: "output_fields" | "status_filter" | "triggers", values: string[]) {
    setForm((f) => ({ ...f, [key]: [...values] }));
  }

  function clearAll(key: "output_fields" | "status_filter" | "triggers") {
    setForm((f) => ({ ...f, [key]: [] }));
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
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEdit() {
    setEditId(null);
    setForm(blank);
  }

  async function save() {
    setError("");
    setMsg("");
    if (!form.name.trim()) {
      setError("Please enter a rule name");
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
        setMsg("Rule updated");
      } else {
        await api.post("/api/feedback-rules", payload);
        setMsg("Rule created");
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
      if (editId === id) cancelEdit();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function toggleEnabled(rule: FeedbackRule, enabled: boolean) {
    try {
      await api.put(`/api/feedback-rules/${rule.id}`, { enabled });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Step / Feedback Rules</h1>
        <p className="page-sub">
          Configure which steps, fields, statuses, and triggers participate in sync and Final Mail
          fetching (not hard-coded to Step 2).
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card rule-form">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">{editId ? "edit" : "add_circle"}</span>
            {editId ? `Edit rule #${editId}` : "New Rule"}
          </h3>
          {editId && (
            <button type="button" className="btn sm secondary" onClick={cancelEdit}>
              <span className="material-symbols-outlined">close</span>
              Cancel edit
            </button>
          )}
        </div>

        {/* Basics */}
        <section className="rule-section">
          <div className="rule-section-title">Basics</div>
          <div className="form-grid">
            <label>
              Name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Step 2 review sync"
              />
            </label>
            <label>
              Priority
              <input
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
              />
              <span className="field-hint">Lower number = higher priority</span>
            </label>
            <label>
              Notes
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Optional"
              />
            </label>
          </div>
        </section>

        {/* Step selection */}
        <section className="rule-section">
          <div className="rule-section-title">Step selection</div>
          <div className="form-grid">
            <label>
              Selector
              <select
                value={form.step_selector}
                onChange={(e) => setForm({ ...form, step_selector: e.target.value })}
              >
                <option value="all">All steps</option>
                <option value="by_index">By index</option>
                <option value="by_name">By name</option>
              </select>
            </label>
            <label>
              Step indexes
              <input
                value={form.step_indexes}
                onChange={(e) => setForm({ ...form, step_indexes: e.target.value })}
                placeholder="e.g. 1,2"
                disabled={form.step_selector !== "by_index"}
              />
              <span className="field-hint">Comma-separated</span>
            </label>
            <label>
              Step names
              <input
                value={form.step_names}
                onChange={(e) => setForm({ ...form, step_names: e.target.value })}
                placeholder="e.g. Step 2, GDS Review"
                disabled={form.step_selector !== "by_name"}
              />
              <span className="field-hint">Comma-separated</span>
            </label>
          </div>
        </section>

        {/* Output fields */}
        <section className="rule-section">
          <div className="rule-section-head">
            <div className="rule-section-title">Output fields</div>
            <div className="rule-section-tools">
              <button
                type="button"
                className="btn sm secondary"
                onClick={() => selectAll("output_fields", DEFAULT_FIELDS)}
              >
                Select all
              </button>
              <button type="button" className="btn sm secondary" onClick={() => clearAll("output_fields")}>
                Clear
              </button>
            </div>
          </div>
          <div className="chip-group option-grid">
            {FIELD_OPTS.map((f) => (
              <label key={f.value} className="md-check-chip" title={f.label}>
                <input
                  type="checkbox"
                  checked={form.output_fields.includes(f.value)}
                  onChange={() => toggleList("output_fields", f.value)}
                />
                <span className="chip-text">{f.label}</span>
              </label>
            ))}
          </div>
        </section>

        {/* Status filter */}
        <section className="rule-section">
          <div className="rule-section-head">
            <div className="rule-section-title">Status filter</div>
            <div className="rule-section-tools">
              <button
                type="button"
                className="btn sm secondary"
                onClick={() => selectAll("status_filter", DEFAULT_STATUS)}
              >
                Select all
              </button>
              <button type="button" className="btn sm secondary" onClick={() => clearAll("status_filter")}>
                Clear
              </button>
            </div>
          </div>
          <div className="chip-group option-grid-status status-chips">
            {STATUS_OPTS.map((s) => (
              <label key={s.value} className="md-check-chip" title={s.label}>
                <input
                  type="checkbox"
                  checked={form.status_filter.includes(s.value)}
                  onChange={() => toggleList("status_filter", s.value)}
                />
                <span className="chip-text">{s.label}</span>
              </label>
            ))}
          </div>
        </section>

        {/* Triggers */}
        <section className="rule-section">
          <div className="rule-section-head">
            <div className="rule-section-title">Triggers</div>
            <div className="rule-section-tools">
              <button
                type="button"
                className="btn sm secondary"
                onClick={() => selectAll(
                  "triggers",
                  TRIGGER_OPTS.map((t) => t.value),
                )}
              >
                Select all
              </button>
              <button type="button" className="btn sm secondary" onClick={() => clearAll("triggers")}>
                Clear
              </button>
            </div>
          </div>
          <div className="chip-group option-grid-triggers">
            {TRIGGER_OPTS.map((t) => (
              <label key={t.value} className="md-check-chip" title={t.label}>
                <input
                  type="checkbox"
                  checked={form.triggers.includes(t.value)}
                  onChange={() => toggleList("triggers", t.value)}
                />
                <span className="chip-text">{t.label}</span>
              </label>
            ))}
          </div>
        </section>

        {/* Options + actions */}
        <section className="rule-section rule-section-last">
          <div className="rule-section-title">Options</div>
          <div className="switch-group">
            <Switch
              checked={form.enabled}
              onChange={(v) => setForm({ ...form, enabled: v })}
              label="Enable rule"
            />
            <Switch
              checked={form.fetch_final_mail}
              onChange={(v) => setForm({ ...form, fetch_final_mail: v })}
              label="Fetch Final Mail comments"
            />
          </div>
        </section>

        <div className="form-footer">
          <div className="form-footer-actions">
            <button type="button" className="btn" onClick={() => void save()}>
              <span className="material-symbols-outlined">save</span>
              {editId ? "Update rule" : "Create rule"}
            </button>
            {editId ? (
              <button type="button" className="btn secondary" onClick={cancelEdit}>
                <span className="material-symbols-outlined">close</span>
                Cancel
              </button>
            ) : (
              <button type="button" className="btn secondary" onClick={() => setForm(blank)}>
                <span className="material-symbols-outlined">restart_alt</span>
                Reset form
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">rule</span>
            Existing Rules
          </h3>
          <span className="badge">{rules.length}</span>
        </div>
        <div className="table-wrap">
          <table className="rules-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Step</th>
                <th>Status filter</th>
                <th>Triggers</th>
                <th className="center">Mail</th>
                <th className="center">Enabled</th>
                <th className="center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className={editId === r.id ? "row-editing" : undefined}>
                  <td>
                    <div className="cell-primary">{r.name}</div>
                    <div className="muted">Priority {r.priority}</div>
                  </td>
                  <td className="mono">
                    {r.step_selector}
                    {r.step_selector === "by_index" ? ` [${r.step_indexes.join(",")}]` : ""}
                    {r.step_selector === "by_name" ? ` [${r.step_names.join(",")}]` : ""}
                  </td>
                  <td>
                    <div className="cell-tags">
                      {(r.status_filter || []).map((s) => (
                        <span key={s} className="badge">
                          {statusLabel(s)}
                        </span>
                      ))}
                      {(r.status_filter || []).length === 0 && <span className="muted">—</span>}
                    </div>
                  </td>
                  <td>
                    <div className="cell-tags">
                      {(r.triggers || []).map((t) => (
                        <span key={t} className="badge">
                          {triggerLabel(t)}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="center">
                    <span className={`badge ${r.fetch_final_mail ? "ok" : "warn"}`}>
                      {r.fetch_final_mail ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="center">
                    <div className="row center">
                      <Switch checked={r.enabled} onChange={(v) => void toggleEnabled(r, v)} />
                    </div>
                  </td>
                  <td className="center">
                    <div className="table-actions">
                      <button
                        type="button"
                        className="btn sm secondary"
                        onClick={() => startEdit(r)}
                        title="Edit"
                      >
                        <span className="material-symbols-outlined">edit</span>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn sm danger"
                        onClick={() => void remove(r.id)}
                        title="Delete"
                      >
                        <span className="material-symbols-outlined">delete</span>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {rules.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    No rules yet. Create one above.
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
