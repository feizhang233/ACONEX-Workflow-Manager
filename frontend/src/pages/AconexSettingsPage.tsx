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
      setMsg("设置已保存（敏感字段已加密存储）");
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
      setMsg("授权地址已生成");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function exchangeCode() {
    setError("");
    setMsg("");
    if (!form.authorization_code.trim()) {
      setError("请输入 Authorization Code");
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
      setMsg(`获取到 ${list.length} 个 Project`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div>
      <h1 className="page-title">ACONEX 设置</h1>
      <p className="page-sub">OAuth 与 API 配置。Client Secret / Token 仅后端加密保存，前端只显示掩码。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack">
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
            Client Secret {publicCfg?.client_secret_masked ? `(当前: ${publicCfg.client_secret_masked})` : ""}
            <input
              type="password"
              autoComplete="new-password"
              placeholder="留空则不修改"
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
            Refresh Token {publicCfg?.refresh_token_masked ? `(当前: ${publicCfg.refresh_token_masked})` : "未设置"}
            <input
              type="password"
              autoComplete="new-password"
              placeholder="可直接粘贴 Refresh Token"
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

        <div className="row">
          <button className="btn" onClick={() => void save()}>
            保存设置
          </button>
          <button className="btn secondary" onClick={() => void genAuthUrl()}>
            生成授权地址
          </button>
          <button className="btn secondary" onClick={() => void testConn()}>
            测试连接
          </button>
          <button className="btn secondary" onClick={() => void loadProjects()}>
            获取 Projects
          </button>
        </div>

        {authUrl && (
          <div>
            <div className="muted">授权地址（在浏览器打开后复制 code）：</div>
            <div className="mono" style={{ wordBreak: "break-all" }}>
              <a href={authUrl} target="_blank" rel="noreferrer">
                {authUrl}
              </a>
            </div>
          </div>
        )}

        <div className="form-grid">
          <label>
            Authorization Code
            <input
              value={form.authorization_code}
              onChange={(e) => set("authorization_code", e.target.value)}
              placeholder="粘贴浏览器回调中的 code"
            />
          </label>
        </div>
        <div className="row">
          <button className="btn" onClick={() => void exchangeCode()}>
            用 Code 交换 Token
          </button>
        </div>

        {publicCfg && (
          <div className="muted">
            Token 状态: access={publicCfg.has_access_token ? "有" : "无"}, refresh=
            {publicCfg.has_refresh_token ? "有" : "无"}
            {publicCfg.access_token_masked ? `, access 掩码 ${publicCfg.access_token_masked}` : ""}
          </div>
        )}

        {projects.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Project ID</th>
                  <th>Name</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.project_id}>
                    <td className="mono">{p.project_id}</td>
                    <td>{p.project_name}</td>
                    <td>
                      <button
                        className="btn sm secondary"
                        onClick={() => {
                          set("project_id", p.project_id);
                          set("project_name", p.project_name);
                        }}
                      >
                        选择
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
