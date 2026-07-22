import { useEffect, useState } from "react";
import { api, type ScheduledJob, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

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
      setMsg("定时任务已创建（持久化到数据库，重启后仍有效）");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function toggle(job: ScheduledJob) {
    try {
      await api.put(`/api/scheduled-jobs/${job.id}`, { enabled: !job.enabled });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function runNow(id: number) {
    try {
      const res = await api.post<{ run_id: number }>(`/api/scheduled-jobs/${id}/run`);
      setMsg(`已触发运行 #${res.run_id}`);
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
    <div>
      <h1 className="page-title">定时任务</h1>
      <p className="page-sub">支持间隔、每天、按星期、Cron。默认时区 Europe/Belgrade。同一任务不会并发重复运行。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack" style={{ marginBottom: "1rem" }}>
        <h3>新建任务</h3>
        <div className="form-grid">
          <label>
            名称
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label>
            任务类型
            <select value={form.job_type} onChange={(e) => setForm({ ...form, job_type: e.target.value })}>
              <option value="pipeline">完整 Pipeline</option>
              <option value="sync_tracked">同步追踪 Workflow</option>
              <option value="sync_current">同步 Current</option>
              <option value="fetch_comments">Final Mail</option>
              <option value="sync_sheets">Google Sheets</option>
            </select>
          </label>
          <label>
            调度类型
            <select
              value={form.schedule_type}
              onChange={(e) => setForm({ ...form, schedule_type: e.target.value })}
            >
              <option value="interval_minutes">每隔 N 分钟</option>
              <option value="interval_hours">每隔 N 小时</option>
              <option value="daily">每天指定时间</option>
              <option value="weekly">指定星期</option>
              <option value="cron">Cron 表达式</option>
            </select>
          </label>
          {(form.schedule_type === "interval_minutes" || form.schedule_type === "interval_hours") && (
            <label>
              间隔值
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
              时间 (HH:MM)
              <input value={form.daily_time} onChange={(e) => setForm({ ...form, daily_time: e.target.value })} />
            </label>
          )}
          {form.schedule_type === "cron" && (
            <label>
              Cron（分 时 日 月 周）
              <input
                value={form.cron_expression}
                onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
              />
            </label>
          )}
          <label>
            时区
            <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </label>
        </div>
        {form.schedule_type === "weekly" && (
          <div className="checkbox-row">
            {WEEKDAYS.map((d) => (
              <label key={d.v}>
                <input type="checkbox" checked={form.weekdays.includes(d.v)} onChange={() => toggleDay(d.v)} />
                {d.l}
              </label>
            ))}
          </div>
        )}
        <div className="row">
          <button className="btn" onClick={() => void create()}>
            创建
          </button>
        </div>
      </div>

      <div className="card">
        <h3>已保存任务</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>名称</th>
                <th>调度</th>
                <th>类型</th>
                <th>上次运行</th>
                <th>下次</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>
                    {j.name}{" "}
                    <span className={`badge ${j.enabled ? "ok" : "warn"}`}>{j.enabled ? "开" : "关"}</span>
                  </td>
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
                  <td className="row">
                    <button className="btn sm secondary" onClick={() => void runNow(j.id)}>
                      立即运行
                    </button>
                    <button className="btn sm secondary" onClick={() => void toggle(j)}>
                      {j.enabled ? "禁用" : "启用"}
                    </button>
                    <button className="btn sm danger" onClick={() => void remove(j.id)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    暂无定时任务
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
