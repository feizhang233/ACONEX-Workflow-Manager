import { useEffect, useState } from "react";
import { api, type GoogleSheetsSettings, ApiError } from "../api/client";
import { Alert } from "../components/Alert";

type Col = { field: string; header: string; order: number };

export function GoogleSheetsPage() {
  const [spreadsheetId, setSpreadsheetId] = useState("");
  const [sheetName, setSheetName] = useState("Workflow Monitor");
  const [saJson, setSaJson] = useState("");
  const [columns, setColumns] = useState<Col[]>([]);
  const [cfg, setCfg] = useState<GoogleSheetsSettings | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  async function load() {
    try {
      const data = await api.get<GoogleSheetsSettings>("/api/settings/google-sheets");
      setCfg(data);
      setSpreadsheetId(data.spreadsheet_id || "");
      setSheetName(data.sheet_name || "Workflow Monitor");
      setColumns(data.column_mapping?.length ? data.column_mapping : []);
      setSaJson("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function save() {
    setError("");
    setMsg("");
    try {
      const body: Record<string, unknown> = {
        spreadsheet_id: spreadsheetId,
        sheet_name: sheetName,
        column_mapping: columns,
      };
      if (saJson.trim()) body.service_account_json = saJson.trim();
      const data = await api.put<GoogleSheetsSettings>("/api/settings/google-sheets", body);
      setCfg(data);
      setSaJson("");
      setMsg("Google Sheets 设置已保存");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function test() {
    setError("");
    setMsg("");
    try {
      const res = await api.post<{ ok: boolean; message: string }>("/api/settings/google-sheets/test");
      if (res.ok) setMsg(res.message);
      else setError(res.message);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  function updateCol(idx: number, patch: Partial<Col>) {
    setColumns((cols) => cols.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }

  function addCol() {
    setColumns((cols) => [...cols, { field: "workflow_number", header: "New Column", order: cols.length }]);
  }

  function removeCol(idx: number) {
    setColumns((cols) => cols.filter((_, i) => i !== idx).map((c, i) => ({ ...c, order: i })));
  }

  return (
    <div>
      <h1 className="page-title">Google Sheets 设置</h1>
      <p className="page-sub">配置 Spreadsheet、Service Account 与输出列。Service Account JSON 仅后端加密保存。</p>
      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack">
        <div className="form-grid">
          <label>
            Spreadsheet ID 或 URL
            <input value={spreadsheetId} onChange={(e) => setSpreadsheetId(e.target.value)} />
          </label>
          <label>
            Sheet 名称
            <input value={sheetName} onChange={(e) => setSheetName(e.target.value)} />
          </label>
        </div>
        <label>
          Service Account JSON
          {cfg?.has_service_account
            ? `（已配置: ${cfg.service_account_email_masked || "***"}）`
            : "（未配置）"}
          <textarea
            placeholder='粘贴完整 JSON，留空则不修改'
            value={saJson}
            onChange={(e) => setSaJson(e.target.value)}
            style={{ minHeight: 140 }}
          />
        </label>

        <div>
          <div className="row" style={{ marginBottom: "0.5rem" }}>
            <h3 style={{ margin: 0 }}>列映射</h3>
            <button className="btn sm secondary" onClick={addCol}>
              添加列
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>顺序</th>
                  <th>字段</th>
                  <th>列名</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {columns.map((c, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        type="number"
                        style={{ width: 70 }}
                        value={c.order}
                        onChange={(e) => updateCol(i, { order: Number(e.target.value) })}
                      />
                    </td>
                    <td>
                      <input value={c.field} onChange={(e) => updateCol(i, { field: e.target.value })} />
                    </td>
                    <td>
                      <input value={c.header} onChange={(e) => updateCol(i, { header: e.target.value })} />
                    </td>
                    <td>
                      <button className="btn sm danger" onClick={() => removeCol(i)}>
                        删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="row">
          <button className="btn" onClick={() => void save()}>
            保存
          </button>
          <button className="btn secondary" onClick={() => void test()}>
            测试连接
          </button>
        </div>
        <p className="muted">
          业务唯一键为 Workflow Number + Step。增量同步只更新变化行；写入失败会保留 pending/failed 状态供重试。
        </p>
      </div>
    </div>
  );
}
