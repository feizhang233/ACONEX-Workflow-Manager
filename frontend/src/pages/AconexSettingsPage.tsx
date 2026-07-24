import { useEffect, useState } from "react";
import { api, type AconexSettings, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

type FormState = {
  authorization_url: string;
  token_url: string;
  base_url: string;
  api_audience: string;
  client_id: string;
  client_secret: string;
  redirect_uri: string;
  authorization_state: string;
  token_auth_method: string;
  project_id: string;
  project_name: string;
  refresh_token: string;
  authorization_code: string;
  default_mail_box: string;
  page_size: number;
};

const empty: FormState = {
  authorization_url: "https://constructionandengineering.oraclecloud.com/auth/authorize",
  token_url: "https://constructionandengineering.oraclecloud.com/auth/token",
  base_url: "https://eu1.aconex.com",
  api_audience: "https://api.aconex.com",
  client_id: "",
  client_secret: "",
  redirect_uri: "http://localhost:8080/callback",
  authorization_state: "aconex-local-auth",
  token_auth_method: "basic",
  project_id: "",
  project_name: "",
  refresh_token: "",
  authorization_code: "",
  default_mail_box: "inbox",
  page_size: 250,
};

export function AconexSettingsPage() {
  const [form, setForm] = useState<FormState>(empty);
  const [publicCfg, setPublicCfg] = useState<AconexSettings | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [authUrl, setAuthUrl] = useState("");
  const [projects, setProjects] = useState<{ project_id: string; project_name: string }[]>([]);

  async function load() {
    try {
      const data = await api.get<AconexSettings>("/api/settings/aconex");
      setPublicCfg(data);
      setForm((f) => ({
        ...f,
        authorization_url: data.authorization_url || f.authorization_url,
        token_url: data.token_url || f.token_url,
        base_url: data.base_url || f.base_url,
        api_audience: data.api_audience || f.api_audience,
        client_id: data.client_id || "",
        client_secret: "",
        redirect_uri: data.redirect_uri || f.redirect_uri,
        authorization_state: data.authorization_state || f.authorization_state,
        token_auth_method: data.token_auth_method || "basic",
        project_id: data.project_id || "",
        project_name: data.project_name || "",
        refresh_token: "",
        authorization_code: "",
        default_mail_box: data.default_mail_box || "inbox",
        page_size: data.page_size || 250,
      }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    setError("");
    setMsg("");
    try {
      const body: Record<string, unknown> = {
        authorization_url: form.authorization_url,
        token_url: form.token_url,
        base_url: form.base_url,
        api_audience: form.api_audience,
        client_id: form.client_id,
        redirect_uri: form.redirect_uri,
        authorization_state: form.authorization_state,
        token_auth_method: form.token_auth_method,
        project_id: form.project_id,
        project_name: form.project_name,
        default_mail_box: form.default_mail_box,
        page_size: form.page_size,
      };
      if (form.client_secret.trim()) body.client_secret = form.client_secret.trim();
      if (form.refresh_token.trim()) body.refresh_token = form.refresh_token.trim();
      const data = await api.put<AconexSettings>("/api/settings/aconex", body);
      setPublicCfg(data);
      setForm((f) => ({ ...f, client_secret: "", refresh_token: "" }));
      setMsg("Settings saved (sensitive fields are encrypted at rest)");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function genAuthUrl() {
    setError("");
    try {
      await save();
      const res = await api.get<{ authorization_url: string }>(
        `/api/settings/aconex/auth-url?redirect_uri=${encodeURIComponent(form.redirect_uri)}`,
      );
      setAuthUrl(res.authorization_url);
      setMsg("Authorization URL generated");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function exchangeCode() {
    setError("");
    setMsg("");
    if (!form.authorization_code.trim()) {
      setError("Please enter an Authorization Code");
      return;
    }
    try {
      const res = await api.post<{ ok: boolean; message: string }>("/api/settings/aconex/exchange-code", {
        code: form.authorization_code.trim(),
        redirect_uri: form.redirect_uri,
      });
      setMsg(res.message);
      setForm((f) => ({ ...f, authorization_code: "" }));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function testConn() {
    setError("");
    setMsg("");
    try {
      const res = await api.post<{ ok: boolean; message: string }>("/api/settings/aconex/test");
      if (res.ok) setMsg(res.message);
      else setError(res.message);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function loadProjects() {
    setError("");
    try {
      const list = await api.get<{ project_id: string; project_name: string }[]>("/api/settings/aconex/projects");
      setProjects(list);
      setMsg(`Loaded ${list.length} project(s)`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">ACONEX Settings</h1>
        <p className="page-sub">
          OAuth and API configuration. Client Secret and tokens are encrypted on the backend; the UI only
          shows masked values.
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="how-it-works">
        <div className="how-it-works-title">
          <span className="material-symbols-outlined">assistant_navigation</span>
          Connect in this order
        </div>
        <div className="mini-flow">
          <div><span>1</span><strong>Enter credentials</strong><small>Client ID, secret, URLs</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span>2</span><strong>Generate auth URL</strong><small>Sign in to Oracle</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span>3</span><strong>Exchange the code</strong><small>Paste the callback code</small></div>
          <span className="material-symbols-outlined">arrow_forward</span>
          <div><span>4</span><strong>Choose & test</strong><small>Select project, test connection</small></div>
        </div>
      </div>

      <div className="card stack">
        <h3>
          <span className="material-symbols-outlined">vpn_key</span>
          OAuth / API Configuration
        </h3>
        <div className="form-grid">
          <label>
            Authorization URL
            <input value={form.authorization_url} onChange={(e) => set("authorization_url", e.target.value)} />
          </label>
          <label>
            Token URL
            <input value={form.token_url} onChange={(e) => set("token_url", e.target.value)} />
          </label>
          <label>
            Base URL
            <input value={form.base_url} onChange={(e) => set("base_url", e.target.value)} />
          </label>
          <label>
            API Audience
            <input value={form.api_audience} onChange={(e) => set("api_audience", e.target.value)} />
          </label>
          <label>
            Client ID
            <input value={form.client_id} onChange={(e) => set("client_id", e.target.value)} />
          </label>
          <label>
            Client Secret {publicCfg?.client_secret_masked ? `(current: ${publicCfg.client_secret_masked})` : ""}
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Leave blank to keep unchanged"
              value={form.client_secret}
              onChange={(e) => set("client_secret", e.target.value)}
            />
          </label>
          <label>
            Redirect URI
            <input value={form.redirect_uri} onChange={(e) => set("redirect_uri", e.target.value)} />
          </label>
          <label>
            Token Auth Method
            <select value={form.token_auth_method} onChange={(e) => set("token_auth_method", e.target.value)}>
              <option value="basic">basic</option>
              <option value="form">form</option>
            </select>
          </label>
          <label>
            Project ID
            <input value={form.project_id} onChange={(e) => set("project_id", e.target.value)} />
          </label>
          <label>
            Project Name
            <input value={form.project_name} onChange={(e) => set("project_name", e.target.value)} />
          </label>
          <label>
            Refresh Token{" "}
            {publicCfg?.refresh_token_masked ? `(current: ${publicCfg.refresh_token_masked})` : "(not set)"}
            <input
              type="password"
              autoComplete="new-password"
              placeholder="Paste Refresh Token directly"
              value={form.refresh_token}
              onChange={(e) => set("refresh_token", e.target.value)}
            />
          </label>
          <label>
            Page Size
            <input
              type="number"
              min={25}
              max={500}
              value={form.page_size}
              onChange={(e) => set("page_size", Number(e.target.value))}
            />
          </label>
        </div>

        <div className="actions">
          <button className="btn" onClick={() => void save()}>
            <span className="material-symbols-outlined">save</span>
            Save Settings
          </button>
          <button className="btn secondary" onClick={() => void genAuthUrl()}>
            <span className="material-symbols-outlined">link</span>
            Generate Auth URL
          </button>
          <button className="btn secondary" onClick={() => void testConn()}>
            <span className="material-symbols-outlined">wifi_tethering</span>
            Test Connection
          </button>
          <button className="btn secondary" onClick={() => void loadProjects()}>
            <span className="material-symbols-outlined">folder_open</span>
            Load Projects
          </button>
        </div>

        {authUrl && (
          <div className="panel-section">
            <div className="section-label">Authorization URL (open in browser, then copy the code)</div>
            <div className="inline-code">
              <a href={authUrl} target="_blank" rel="noreferrer">
                {authUrl}
              </a>
            </div>
          </div>
        )}

        <div className="divider" />

        <div className="form-grid">
          <label>
            Authorization Code
            <input
              value={form.authorization_code}
              onChange={(e) => set("authorization_code", e.target.value)}
              placeholder="Paste code from browser callback"
            />
          </label>
        </div>
        <div className="actions">
          <button className="btn tonal" onClick={() => void exchangeCode()}>
            <span className="material-symbols-outlined">sync_alt</span>
            Exchange Code for Token
          </button>
        </div>

        {publicCfg && (
          <div className="meta-pills">
            <span className={`badge ${publicCfg.has_access_token ? "ok" : "warn"}`}>
              Access Token: {publicCfg.has_access_token ? "Yes" : "No"}
            </span>
            <span className={`badge ${publicCfg.has_refresh_token ? "ok" : "warn"}`}>
              Refresh Token: {publicCfg.has_refresh_token ? "Yes" : "No"}
            </span>
            {publicCfg.access_token_masked && (
              <span className="muted mono">masked {publicCfg.access_token_masked}</span>
            )}
          </div>
        )}

        {projects.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Project ID</th>
                  <th>Name</th>
                  <th className="center"></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.project_id}>
                    <td className="mono">{p.project_id}</td>
                    <td>{p.project_name}</td>
                    <td className="center">
                      <button
                        className="btn sm secondary"
                        onClick={() => {
                          set("project_id", p.project_id);
                          set("project_name", p.project_name);
                        }}
                      >
                        Select
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
