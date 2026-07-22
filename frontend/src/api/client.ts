/** Typed API client. Secrets are never stored in localStorage. */

const API_BASE = import.meta.env.VITE_API_BASE || "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(msg || `HTTP ${res.status}`, res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export type AconexSettings = {
  authorization_url: string;
  token_url: string;
  base_url: string;
  api_audience: string;
  client_id: string;
  client_secret_masked: string | null;
  redirect_uri: string;
  authorization_state: string;
  token_auth_method: string;
  project_id: string;
  project_name: string;
  has_refresh_token: boolean;
  has_access_token: boolean;
  refresh_token_masked: string | null;
  access_token_masked: string | null;
  token_expires_at: string | null;
  default_mail_box: string;
  page_size: number;
  updated_at: string | null;
};

export type GoogleSheetsSettings = {
  spreadsheet_id: string;
  sheet_name: string;
  has_service_account: boolean;
  service_account_email_masked: string | null;
  column_mapping: { field: string; header: string; order: number }[];
  updated_at: string | null;
};

export type TrackedWorkflow = {
  id: number;
  workflow_number: string;
  workflow_number_int: number | null;
  enabled: boolean;
  notes: string;
  created_at: string | null;
  updated_at: string | null;
};

export type WorkflowStep = {
  id: number;
  workflow_id: string;
  workflow_number: string;
  step_index: number | null;
  step_name: string;
  step_status: string;
  step_outcome: string;
  participant: string;
  date_due: string;
  date_completed: string;
  date_in: string;
  overdue: string;
  final_mail_comment: string;
  sheet_sync_status: string;
  sheet_sync_error: string;
  last_synced_to_sheet_at: string | null;
  updated_at: string | null;
};

export type Workflow = {
  id: number;
  workflow_id: string;
  workflow_number: string;
  workflow_number_int: number | null;
  workflow_title: string;
  review_status: string;
  review_outcome: string;
  is_completed: boolean;
  is_current: boolean;
  last_checked_at: string | null;
  last_changed_at: string | null;
  source: string;
  steps: WorkflowStep[];
};

export type FeedbackRule = {
  id: number;
  name: string;
  enabled: boolean;
  step_selector: string;
  step_indexes: number[];
  step_names: string[];
  output_fields: string[];
  status_filter: string[];
  triggers: string[];
  fetch_final_mail: boolean;
  priority: number;
  notes: string;
  created_at: string | null;
  updated_at: string | null;
};

export type ScheduledJob = {
  id: number;
  name: string;
  enabled: boolean;
  schedule_type: string;
  interval_value: number | null;
  daily_time: string | null;
  weekdays: number[];
  cron_expression: string | null;
  timezone: string;
  job_type: string;
  job_params: Record<string, unknown>;
  last_run_at: string | null;
  last_run_status: string;
  next_run_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type RunLog = {
  id: number;
  timestamp: string;
  level: string;
  stage: string;
  message: string;
};

export type UpdateRun = {
  id: number;
  command: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  checked_count: number;
  updated_count: number;
  failed_count: number;
  sheet_synced_count: number;
  progress_pct: number;
  current_stage: string;
  error_message: string;
  notes: string;
  triggered_by: string;
  scheduled_job_id: number | null;
  parent_run_id: number | null;
  logs: RunLog[];
};

export type DashboardStats = {
  tracked_count: number;
  tracked_enabled: number;
  workflow_count: number;
  current_count: number;
  pending_sheet_sync: number;
  failed_sheet_sync: number;
  last_run: UpdateRun | null;
  active_run: UpdateRun | null;
  aconex_configured: boolean;
  sheets_configured: boolean;
  scheduled_jobs_enabled: number;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type WorkflowHistory = {
  id: number;
  workflow_id: string;
  workflow_number: string;
  step_index: number | null;
  step_name: string;
  change_type: string;
  change_summary: string;
  old_data_json: string;
  new_data_json: string;
  checked_at: string;
};
