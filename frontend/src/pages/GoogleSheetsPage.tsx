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
      setMsg("Google Sheets settings saved");
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
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Google Sheets Settings</h1>
        <p className="page-sub">
          Configure spreadsheet, service account, and output columns. Service Account JSON is encrypted on
          the backend only.
        </p>
      </header>

      <Alert type="error">{error}</Alert>
      <Alert type="success">{msg}</Alert>

      <div className="card stack">
        <h3>
          <span className="material-symbols-outlined">table_chart</span>
          Spreadsheet Configuration
        </h3>
        <div className="form-grid">
          <label>
            Spreadsheet ID or URL
            <input value={spreadsheetId} onChange={(e) => setSpreadsheetId(e.target.value)} />
          </label>
          <label>
            Sheet name
            <input value={sheetName} onChange={(e) => setSheetName(e.target.value)} />
          </label>
        </div>
        <label>
          Service Account JSON
          {cfg?.has_service_account
            ? ` (configured: ${cfg.service_account_email_masked || "***"})`
            : " (not configured)"}
          <textarea
            placeholder="Paste full JSON; leave blank to keep unchanged"
            value={saJson}
            onChange={(e) => setSaJson(e.target.value)}
            style={{ minHeight: 140 }}
          />
        </label>

        <div className="divider" />

        <div className="card-header">
          <h3 style={{ margin: 0 }}>
            <span className="material-symbols-outlined">view_column</span>
            Column Mapping
          </h3>
          <button className="btn sm secondary" onClick={addCol}>
            <span className="material-symbols-outlined">add</span>
            Add Column
          </button>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 90 }}>Order</th>
                <th>Field</th>
                <th>Header</th>
                <th className="center" style={{ width: 100 }}></th>
              </tr>
            </thead>
            <tbody>
              {columns.map((c, i) => (
                <tr key={i}>
                  <td>
                    <input
                      type="number"
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
                  <td className="center">
                    <button className="btn sm danger" onClick={() => removeCol(i)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {columns.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty-cell">
                    No column mapping yet. Click &quot;Add Column&quot; to start.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="actions">
          <button className="btn" onClick={() => void save()}>
            <span className="material-symbols-outlined">save</span>
            Save
          </button>
          <button className="btn secondary" onClick={() => void test()}>
            <span className="material-symbols-outlined">wifi_tethering</span>
            Test Connection
          </button>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Business key is Workflow Number + Step. Incremental sync only updates changed rows; write failures
          keep pending/failed status for retry.
        </p>
      </div>
    </div>
  );
}
