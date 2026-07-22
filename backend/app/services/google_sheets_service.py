"""Google Sheets configuration and sync (idempotent by Workflow Number + Step)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import GoogleSheetsSettings, SyncQueueItem, WorkflowStep, utc_now
from app.services.encryption import decrypt_value, encrypt_value, mask_secret
from app.services.feedback_service import collect_sync_rows


LogFn = Callable[[str, str, str], None]


def _noop_log(level: str, stage: str, message: str) -> None:
    pass


DEFAULT_COLUMNS = [
    {"field": "workflow_number", "header": "Workflow Number", "order": 0},
    {"field": "workflow_title", "header": "Workflow Title", "order": 1},
    {"field": "step_name", "header": "Step", "order": 2},
    {"field": "step_status", "header": "Status", "order": 3},
    {"field": "step_outcome", "header": "Outcome", "order": 4},
    {"field": "participant", "header": "Participant", "order": 5},
    {"field": "date_due", "header": "Due Date", "order": 6},
    {"field": "date_completed", "header": "Completed Date", "order": 7},
    {"field": "overdue", "header": "Overdue", "order": 8},
    {"field": "final_mail_comment", "header": "Final Mail Comment", "order": 9},
]


class GoogleSheetsError(RuntimeError):
    pass


def get_or_create_settings(db: Session) -> GoogleSheetsSettings:
    row = db.query(GoogleSheetsSettings).filter(GoogleSheetsSettings.id == 1).first()
    if row is None:
        row = GoogleSheetsSettings(id=1, column_mapping_json=json.dumps(DEFAULT_COLUMNS))
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def public_settings(db: Session) -> dict[str, Any]:
    row = get_or_create_settings(db)
    email_masked = None
    has_sa = bool(row.service_account_json_enc)
    if has_sa:
        try:
            raw = decrypt_value(row.service_account_json_enc) or "{}"
            payload = json.loads(raw)
            email = payload.get("client_email") or ""
            email_masked = mask_secret(email, visible=12) if email else "***"
        except Exception:
            email_masked = "***"
    try:
        columns = json.loads(row.column_mapping_json or "[]")
    except json.JSONDecodeError:
        columns = DEFAULT_COLUMNS
    return {
        "spreadsheet_id": row.spreadsheet_id or "",
        "sheet_name": row.sheet_name or "Workflow Monitor",
        "has_service_account": has_sa,
        "service_account_email_masked": email_masked,
        "column_mapping": columns,
        "updated_at": row.updated_at,
    }


def update_settings(db: Session, data: dict[str, Any]) -> GoogleSheetsSettings:
    row = get_or_create_settings(db)
    if data.get("spreadsheet_id") is not None:
        row.spreadsheet_id = data["spreadsheet_id"]
    if data.get("sheet_name") is not None:
        row.sheet_name = data["sheet_name"]
    if data.get("service_account_json"):
        # Validate JSON
        json.loads(data["service_account_json"])
        row.service_account_json_enc = encrypt_value(data["service_account_json"])
    if data.get("column_mapping") is not None:
        mapping = data["column_mapping"]
        if isinstance(mapping, list):
            row.column_mapping_json = json.dumps(mapping)
    row.updated_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _build_sheets_service(service_account_json: str):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(service_account_json)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def test_connection(db: Session) -> dict[str, Any]:
    row = get_or_create_settings(db)
    if not row.spreadsheet_id:
        return {"ok": False, "message": "Spreadsheet ID is not configured.", "detail": {}}
    if not row.service_account_json_enc:
        return {"ok": False, "message": "Service account JSON is not configured.", "detail": {}}
    try:
        sa = decrypt_value(row.service_account_json_enc) or ""
        service = _build_sheets_service(sa)
        meta = (
            service.spreadsheets()
            .get(spreadsheetId=row.spreadsheet_id, fields="properties.title,sheets.properties.title")
            .execute()
        )
        titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
        return {
            "ok": True,
            "message": f"Connected to spreadsheet: {meta.get('properties', {}).get('title', '')}",
            "detail": {"sheets": titles, "target_sheet": row.sheet_name},
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc), "detail": {}}


def _biz_key(workflow_number: str, step_index: Any, step_name: str) -> str:
    return f"{workflow_number}|{step_index if step_index is not None else ''}|{step_name or ''}"


def _row_values(row: dict[str, Any], columns: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(columns, key=lambda c: c.get("order", 0))
    return [str(row.get(c["field"], "") if row.get(c["field"]) is not None else "") for c in ordered]


def _headers(columns: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(columns, key=lambda c: c.get("order", 0))
    return [c.get("header") or c.get("field", "") for c in ordered]


class GoogleSheetsGateway:
    """Thin wrapper used by sync logic; injectable for tests."""

    def __init__(self, service: Any, spreadsheet_id: str, sheet_name: str):
        self.service = service
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name

    def read_all(self) -> list[list[str]]:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=f"'{self.sheet_name}'")
            .execute()
        )
        return result.get("values") or []

    def write_range(self, start_a1: str, values: list[list[str]]) -> None:
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{self.sheet_name}'!{start_a1}",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    def append_rows(self, values: list[list[str]]) -> None:
        if not values:
            return
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{self.sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()

    def ensure_headers(self, headers: list[str]) -> None:
        existing = self.read_all()
        if not existing:
            self.write_range("A1", [headers])
            return
        # If first row differs, rewrite headers only when empty sheet body
        if existing[0] != headers and len(existing) == 1:
            self.write_range("A1", [headers])


def sync_to_sheets(
    db: Session,
    *,
    full: bool = False,
    gateway: GoogleSheetsGateway | None = None,
    log: LogFn = _noop_log,
) -> dict[str, int]:
    """Incremental or full sync. Business key = workflow_number + step.

    On write failure, mark steps/queue as failed for retry.
    """
    row = get_or_create_settings(db)
    if not row.spreadsheet_id or not row.service_account_json_enc:
        raise GoogleSheetsError("Google Sheets is not fully configured.")

    try:
        columns = json.loads(row.column_mapping_json or "[]") or DEFAULT_COLUMNS
    except json.JSONDecodeError:
        columns = DEFAULT_COLUMNS

    data_rows = collect_sync_rows(db, force_all=full)
    if not data_rows and not full:
        # Still retry previously failed queue items
        data_rows = _rows_from_failed_queue(db)
    if not data_rows and full:
        # Full mode: all steps regardless of pending
        data_rows = collect_sync_rows(db, force_all=True)

    log("INFO", "sheets", f"Preparing {len(data_rows)} row(s) for Google Sheets (full={full}).")

    if gateway is None:
        sa = decrypt_value(row.service_account_json_enc) or ""
        service = _build_sheets_service(sa)
        gateway = GoogleSheetsGateway(service, row.spreadsheet_id, row.sheet_name or "Workflow Monitor")

    headers = _headers(columns)
    # Ensure workflow_number and step_name columns exist for key matching
    field_names = [c["field"] for c in sorted(columns, key=lambda c: c.get("order", 0))]
    try:
        wn_idx = field_names.index("workflow_number")
    except ValueError:
        wn_idx = 0
    try:
        step_idx_col = field_names.index("step_name")
    except ValueError:
        try:
            step_idx_col = field_names.index("step_index")
        except ValueError:
            step_idx_col = 1 if len(field_names) > 1 else 0

    try:
        gateway.ensure_headers(headers)
        existing = gateway.read_all()
    except Exception as exc:
        _mark_rows_failed(db, data_rows, str(exc))
        raise GoogleSheetsError(f"Failed to read sheet: {exc}") from exc

    # Map existing body rows by business key -> 1-based sheet row number
    key_to_rownum: dict[str, int] = {}
    for i, values in enumerate(existing[1:], start=2):  # row 1 = header
        if not values:
            continue
        wn = values[wn_idx] if wn_idx < len(values) else ""
        step_part = values[step_idx_col] if step_idx_col < len(values) else ""
        key_to_rownum[f"{wn}|{step_part}"] = i

    updates: list[tuple[int, list[str]]] = []
    appends: list[list[str]] = []
    synced_step_ids: list[int] = []
    failed = 0

    for data in data_rows:
        values = _row_values(data, columns)
        wn = str(data.get("workflow_number") or "")
        step_name = str(data.get("step_name") or data.get("step_index") or "")
        # Key for matching existing rows uses displayed step column value
        display_step = str(data.get("step_name") or data.get("step_index") or "")
        if "step_name" in field_names:
            display_step = str(data.get("step_name") or "")
        elif "step_index" in field_names:
            display_step = str(data.get("step_index") or "")
        key = f"{wn}|{display_step}"
        if key in key_to_rownum:
            updates.append((key_to_rownum[key], values))
        else:
            appends.append(values)
            # Reserve key so duplicates in same batch don't double-append
            key_to_rownum[key] = -1
        if data.get("_step_id"):
            synced_step_ids.append(int(data["_step_id"]))

    try:
        for row_num, values in updates:
            gateway.write_range(f"A{row_num}", [values])
        if appends:
            gateway.append_rows(appends)
    except Exception as exc:
        _mark_rows_failed(db, data_rows, str(exc))
        raise GoogleSheetsError(f"Failed to write sheet: {exc}") from exc

    now = utc_now()
    if synced_step_ids:
        steps = db.query(WorkflowStep).filter(WorkflowStep.id.in_(synced_step_ids)).all()
        for step in steps:
            step.sheet_sync_status = "synced"
            step.sheet_sync_error = ""
            step.last_synced_to_sheet_at = now
            db.add(step)
        # Clear queue items
        for data in data_rows:
            step_key = _biz_key(
                str(data.get("workflow_number") or ""),
                data.get("step_index"),
                str(data.get("step_name") or ""),
            )
            q = (
                db.query(SyncQueueItem)
                .filter(
                    SyncQueueItem.workflow_number == str(data.get("workflow_number") or ""),
                    SyncQueueItem.step_key == step_key,
                )
                .first()
            )
            if q:
                q.status = "synced"
                q.synced_at = now
                q.error_message = ""
                db.add(q)
        db.commit()

    log(
        "INFO",
        "sheets",
        f"Sheet sync done: updated={len(updates)} appended={len(appends)} failed={failed}",
    )
    return {
        "checked": len(data_rows),
        "updated": len(updates),
        "appended": len(appends),
        "synced": len(updates) + len(appends),
        "failed": failed,
    }


def _mark_rows_failed(db: Session, data_rows: list[dict[str, Any]], error: str) -> None:
    now = utc_now()
    for data in data_rows:
        step_id = data.get("_step_id")
        if step_id:
            step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
            if step:
                step.sheet_sync_status = "failed"
                step.sheet_sync_error = error[:1000]
                db.add(step)
        wn = str(data.get("workflow_number") or "")
        step_key = _biz_key(wn, data.get("step_index"), str(data.get("step_name") or ""))
        q = (
            db.query(SyncQueueItem)
            .filter(SyncQueueItem.workflow_number == wn, SyncQueueItem.step_key == step_key)
            .first()
        )
        if q is None:
            q = SyncQueueItem(
                workflow_number=wn,
                step_key=step_key,
                step_index=data.get("step_index"),
                step_name=str(data.get("step_name") or ""),
                payload_json=json.dumps(data, default=str),
                status="failed",
                error_message=error[:1000],
                attempts=1,
            )
        else:
            q.status = "failed"
            q.error_message = error[:1000]
            q.attempts = (q.attempts or 0) + 1
            q.updated_at = now
        db.add(q)
    db.commit()


def _rows_from_failed_queue(db: Session) -> list[dict[str, Any]]:
    items = (
        db.query(SyncQueueItem)
        .filter(SyncQueueItem.status.in_(["pending", "failed"]))
        .all()
    )
    rows: list[dict[str, Any]] = []
    for item in items:
        try:
            payload = json.loads(item.payload_json or "{}")
        except json.JSONDecodeError:
            continue
        if payload:
            rows.append(payload)
    # Also include pending steps not yet queued
    pending_steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.sheet_sync_status.in_(["pending", "failed"]))
        .all()
    )
    existing_keys = {
        f"{r.get('workflow_number')}|{r.get('step_index')}|{r.get('step_name')}" for r in rows
    }
    from app.services.feedback_service import collect_sync_rows as _collect

    for row in _collect(db, force_all=False):
        key = f"{row.get('workflow_number')}|{row.get('step_index')}|{row.get('step_name')}"
        if key not in existing_keys:
            rows.append(row)
            existing_keys.add(key)
    # silence unused
    _ = pending_steps
    return rows
