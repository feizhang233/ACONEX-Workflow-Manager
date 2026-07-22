import { useEffect, useState } from "react";
import { api, type ScheduledJob, ApiError } from "../api/client";
import { Alert } from "../components/Alert";
import { Switch } from "../components/Switch";

type Form = {
  name: string;
  enabled: boolean;
  schedule_type: string;
  interval_value: number;
  daily_time: string;
  weekdays: number[];
  cron_expression: string;
  timezone: string;
  job_type: string;
};

const blank: Form = {
  name: "Daily pipeline",
  enabled: true,
  schedule_type: "weekly",
  interval_value: 60,
  daily_time: "10:00",
  weekdays: [0, 1, 2, 3, 4],
  cron_expression: "0 10 * * 1-5",
  timezone: "Europe/Belgrade",
  job_type: "pipeline",
};

const WEEKDAYS = [
  { v: 0, l: "Mon" },
  { v: 1, l: "Tue" },
  { v: 2, l: "Wed" },
  { v: 3, l: "Thu" },
  { v: 4, l: "Fri" },
  { v: 5, l: "Sat" },
  { v: 6, l: "Sun" },
];

export function ScheduledJobsPage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [form, setForm] = useState<Form>(blank);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      setJobs(await api.get<ScheduledJob[]>("/api/scheduled-jobs"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function create() {
    setError("");
    setMsg("");
    try {
      await api.post("/api/scheduled-jobs", {
        name: form.name,
        enabled: form.enabled,
        schedule_type: form.schedule_type,
        interval_value: form.interval_value,
        daily_time: form.daily_time,
        weekdays: form.weekdays,
        cron_expression: form.cron_expression,
        timezone: form.timezone,
        job_type: form.job_type,
      });
      setMsg("Scheduled job created (persisted in DB, survives restarts)");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function toggle(job: ScheduledJob, enabled: boolean) {
    try {
      await api.put(`/api/scheduled-jobs/${job.id}`, { enabled });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function runNow(id: number) {
    try {
      const res = await api.post<{ run_id: number }>(`/api/scheduled-jobs/${id}/run`);
      setMsg(`Triggered run #${res.run_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/api/scheduled-jobs/${id}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  function toggleDay(d: number) {
    setForm((f) => ({
      ...f,
      weekdays: f.weekdays.includes(d) ? f.weekdays.filter((x) => x !== d) : [...f.weekdays, d].sort(),
    }));
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Scheduled Jobs</h1>
        <p className="page-sub">
          Supports interval, daily, weekly, and Cron schedules. Default timezone is Europe/Belgrade.
          The same job will not run concurrently.
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack">
        <h3>
          <span className="material-symbols-outlined">add_alarm</span>
          New Job
        </h3>
        <div className="form-grid">
          <label>
            Name
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label>
            Job type
            <select value={form.job_type} onChange={(e) => setForm({ ...form, job_type: e.target.value })}>
              <option value="pipeline">Full Pipeline</option>
              <option value="sync_tracked">Sync Tracked Workflows</option>
              <option value="sync_current">Sync Current</option>
              <option value="fetch_comments">Final Mail</option>
              <option value="sync_sheets">Google Sheets</option>
            </select>
          </label>
          <label>
            Schedule type
            <select
              value={form.schedule_type}
              onChange={(e) => setForm({ ...form, schedule_type: e.target.value })}
            >
              <option value="interval_minutes">Every N minutes</option>
              <option value="interval_hours">Every N hours</option>
              <option value="daily">Daily at time</option>
              <option value="weekly">Weekly on days</option>
              <option value="cron">Cron expression</option>
            </select>
          </label>
          {(form.schedule_type === "interval_minutes" || form.schedule_type === "interval_hours") && (
            <label>
              Interval value
              <input
                type="number"
                min={1}
                value={form.interval_value}
                onChange={(e) => setForm({ ...form, interval_value: Number(e.target.value) })}
              />
            </label>
          )}
          {(form.schedule_type === "daily" || form.schedule_type === "weekly") && (
            <label>
              Time (HH:MM)
              <input value={form.daily_time} onChange={(e) => setForm({ ...form, daily_time: e.target.value })} />
            </label>
          )}
          {form.schedule_type === "cron" && (
            <label>
              Cron (min hour day month weekday)
              <input
                value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
              />
            </label>
          )}
          <label>
            Timezone
            <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </label>
        </div>

        {form.schedule_type === "weekly" && (
          <div className="panel-section">
            <div className="section-label">Weekdays</div>
            <div className="chip-group">
              {WEEKDAYS.map((d) => (
                <label key={d.v} className="md-check-chip">
                  <input
                    type="checkbox"
                    checked={form.weekdays.includes(d.v)}
                    onChange={() => toggleDay(d.v)}
                  />
                  {d.l}
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="switch-group">
          <Switch
            checked={form.enabled}
            onChange={(v) => setForm({ ...form, enabled: v })}
            label="Enable after create"
          />
        </div>

        <div className="actions">
          <button className="btn" onClick={() => void create()}>
            <span className="material-symbols-outlined">add</span>
            Create
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>
            <span className="material-symbols-outlined">schedule</span>
            Saved Jobs
          </h3>
          <span className="badge">{jobs.length}</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Schedule</th>
                <th>Type</th>
                <th>Last run</th>
                <th>Next</th>
                <th className="center">Enabled</th>
                <th className="center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>{j.name}</td>
                  <td className="mono">
                    {j.schedule_type}
                    {j.interval_value ? ` ${j.interval_value}` : ""}
                    {j.daily_time ? ` ${j.daily_time}` : ""}
                    {j.cron_expression ? ` ${j.cron_expression}` : ""}
                    <div className="muted">{j.timezone}</div>
                  </td>
                  <td>{j.job_type}</td>
                  <td>
                    {j.last_run_at || "—"}
                    {j.last_run_status ? ` (${j.last_run_status})` : ""}
                  </td>
                  <td>{j.next_run_at || "—"}</td>
                  <td className="center">
                    <div className="row center">
                      <Switch checked={j.enabled} onChange={(v) => void toggle(j, v)} />
                    </div>
                  </td>
                  <td className="center">
                    <div className="row center">
                      <button className="btn sm secondary" onClick={() => void runNow(j.id)}>
                        Run now
                      </button>
                      <button className="btn sm danger" onClick={() => void remove(j.id)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    No scheduled jobs
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
