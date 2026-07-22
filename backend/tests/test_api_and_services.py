"""API and service integration tests with mocks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.aconex.auth import AconexAuthService
from app.services.encryption import encrypt_value, decrypt_value, mask_secret
from app.services.feedback_service import ensure_default_rule, rule_matches_step, create_rule
from app.services.workflow_service import add_tracked_numbers, upsert_workflow_steps
from app.services.aconex.xml_utils import parse_workflow_xml
from app.services.google_sheets_service import GoogleSheetsGateway, sync_to_sheets
from app.models.entities import WorkflowStep
from tests.conftest import SAMPLE_WORKFLOW_XML, SAMPLE_MAIL_LIST_XML, SAMPLE_MAIL_DETAIL_XML


def test_encryption_roundtrip():
    plain = "super-secret-token-value"
    enc = encrypt_value(plain)
    assert enc != plain
    assert decrypt_value(enc) == plain
    assert "*" in (mask_secret(plain) or "")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_aconex_settings_masking(client, db_session):
    # Use API via client which has its own session — put via API
    r = client.put(
        "/api/settings/aconex",
        json={
            "authorization_url": "https://example.com/auth",
            "token_url": "https://example.com/token",
            "base_url": "https://eu1.aconex.com",
            "client_id": "my-client",
            "client_secret": "secret-abc-12345",
            "refresh_token": "refresh-token-xyz-999",
            "project_id": "P1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["client_id"] == "my-client"
    assert data["client_secret_masked"] is not None
    assert "secret" not in (data["client_secret_masked"] or "").lower() or "*" in data["client_secret_masked"]
    assert data["has_refresh_token"] is True
    assert "refresh-token-xyz" not in str(data)
    # GET again
    g = client.get("/api/settings/aconex")
    assert g.status_code == 200
    assert g.json()["has_refresh_token"] is True
    assert "refresh-token-xyz-999" not in g.text


def test_auth_url(client):
    client.put(
        "/api/settings/aconex",
        json={
            "authorization_url": "https://example.com/auth",
            "client_id": "cid",
            "redirect_uri": "http://localhost:8080/callback",
        },
    )
    r = client.get("/api/settings/aconex/auth-url")
    assert r.status_code == 200
    url = r.json()["authorization_url"]
    assert "client_id=cid" in url
    assert "response_type=code" in url


def test_tracked_workflows_batch(client):
    r = client.post(
        "/api/tracked-workflows/batch",
        json={"text": "800-802", "enabled": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 3
    listed = client.get("/api/tracked-workflows")
    assert listed.status_code == 200
    assert len(listed.json()) == 3


def test_tracked_enable_delete(client):
    client.post("/api/tracked-workflows", json={"workflow_number": "WF-850"})
    items = client.get("/api/tracked-workflows").json()
    tid = items[0]["id"]
    r = client.patch(f"/api/tracked-workflows/{tid}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    d = client.delete(f"/api/tracked-workflows/{tid}")
    assert d.status_code == 200


def test_feedback_rules_crud(client):
    r = client.get("/api/feedback-rules")
    assert r.status_code == 200
    assert len(r.json()) >= 1  # default rule
    created = client.post(
        "/api/feedback-rules",
        json={
            "name": "Step2 only",
            "step_selector": "by_index",
            "step_indexes": [2],
            "triggers": ["pending_to_final"],
            "fetch_final_mail": True,
        },
    )
    assert created.status_code == 200
    rid = created.json()["id"]
    updated = client.put(
        f"/api/feedback-rules/{rid}",
        json={"enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    deleted = client.delete(f"/api/feedback-rules/{rid}")
    assert deleted.status_code == 200


def test_upsert_workflow_steps_and_history(db_session):
    page = parse_workflow_xml(SAMPLE_WORKFLOW_XML)
    counts = upsert_workflow_steps(db_session, page.steps, source="test")
    assert counts["checked"] >= 2
    from app.models.entities import Workflow, WorkflowHistory

    wfs = db_session.query(Workflow).all()
    assert len(wfs) == 2
    steps = db_session.query(WorkflowStep).all()
    assert len(steps) >= 3
    # Second upsert without changes should not explode
    counts2 = upsert_workflow_steps(db_session, page.steps, source="test")
    assert counts2["checked"] >= 2
    # Change status and ensure history
    page.steps[1].step_outcome = "A"
    page.steps[1].step_status = "Completed"
    upsert_workflow_steps(db_session, page.steps, source="test")
    history = db_session.query(WorkflowHistory).all()
    assert any(h.change_type in {"status", "new"} for h in history)


def test_sync_with_mock_aconex(db_session):
    """Sync pipeline services with mocked ACONEX client (no real network)."""

    class FakeResponse:
        def __init__(self, content: bytes, status_code: int = 200):
            self.content = content
            self.status_code = status_code
            self.text = content.decode()
            self.headers = {"content-type": "application/xml"}

    class FakeClient:
        def close(self):
            pass

        def fetch_workflow_page(self, **kwargs):
            return FakeResponse(SAMPLE_WORKFLOW_XML)

        def fetch_mail_page(self, **kwargs):
            return FakeResponse(SAMPLE_MAIL_LIST_XML)

        def fetch_mail_detail(self, mail_id):
            return FakeResponse(SAMPLE_MAIL_DETAIL_XML)

    from app.services.run_service import create_run, finish_run, make_run_logger, update_progress
    from app.services.workflow_service import sync_current_workflows
    from app.services.mail_service import scan_final_mail
    from app.services.feedback_service import ensure_default_rule

    ensure_default_rule(db_session)
    run = create_run(db_session, "pipeline", triggered_by="test")
    log = make_run_logger(db_session, run.id)
    fake = FakeClient()
    update_progress(db_session, run.id, progress_pct=10, stage="sync")
    counts = sync_current_workflows(db_session, fake, max_pages=1, log=log)
    update_progress(db_session, run.id, progress_pct=50, stage="mail")
    m = scan_final_mail(db_session, fake, max_pages=1, log=log)
    finish_run(db_session, run.id, status="success")

    assert counts["checked"] >= 1
    from app.models.entities import Workflow, UpdateRun

    assert db_session.query(Workflow).count() >= 1
    done = db_session.query(UpdateRun).filter(UpdateRun.id == run.id).first()
    assert done is not None
    assert done.status == "success"
    assert m["checked"] >= 0


def test_google_sheets_idempotent_sync(db_session):
    page = parse_workflow_xml(SAMPLE_WORKFLOW_XML)
    upsert_workflow_steps(db_session, page.steps, source="test")
    ensure_default_rule(db_session)

    # Fake gateway that tracks writes
    store: list[list[str]] = []

    class FakeGateway(GoogleSheetsGateway):
        def __init__(self):
            self.service = None
            self.spreadsheet_id = "sheet"
            self.sheet_name = "WF"

        def read_all(self):
            return store[:]

        def write_range(self, start_a1, values):
            # simplistic: only A1 header or single row updates
            if start_a1 == "A1":
                if not store:
                    store.extend(values)
                else:
                    store[0] = values[0]
                return
            # A{n}
            row_num = int(start_a1[1:])
            while len(store) < row_num:
                store.append([])
            store[row_num - 1] = values[0]

        def append_rows(self, values):
            store.extend(values)

        def ensure_headers(self, headers):
            if not store:
                store.append(headers)
            elif store[0] != headers and len(store) == 1:
                store[0] = headers

    from app.services import google_sheets_service as gsvc

    row = gsvc.get_or_create_settings(db_session)
    row.spreadsheet_id = "abc"
    row.service_account_json_enc = encrypt_value('{"client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}')
    db_session.add(row)
    db_session.commit()

    gw = FakeGateway()
    r1 = sync_to_sheets(db_session, full=True, gateway=gw)
    assert r1["synced"] >= 1
    rows_after_first = len(store)
    # Mark steps pending again and re-sync — should update, not duplicate by key
    for step in db_session.query(WorkflowStep).all():
        step.sheet_sync_status = "pending"
        db_session.add(step)
    db_session.commit()
    r2 = sync_to_sheets(db_session, full=False, gateway=gw)
    # Appends should be 0 if keys matched; row count stable or only updates
    assert r2["appended"] == 0
    assert len(store) == rows_after_first


def test_scheduled_job_api(client):
    r = client.post(
        "/api/scheduled-jobs",
        json={
            "name": "Daily pipeline",
            "schedule_type": "daily",
            "daily_time": "10:00",
            "timezone": "Europe/Belgrade",
            "job_type": "pipeline",
            "enabled": True,
        },
    )
    assert r.status_code == 200
    job_id = r.json()["id"]
    listed = client.get("/api/scheduled-jobs")
    assert any(j["id"] == job_id for j in listed.json())
    client.put(f"/api/scheduled-jobs/{job_id}", json={"enabled": False})
    client.delete(f"/api/scheduled-jobs/{job_id}")
    assert client.get("/api/scheduled-jobs").json() == []


def test_dashboard(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert "tracked_count" in data
    assert "aconex_configured" in data


def test_sheets_settings(client):
    r = client.put(
        "/api/settings/google-sheets",
        json={
            "spreadsheet_id": "https://docs.google.com/spreadsheets/d/SPREADSHEET123/edit",
            "sheet_name": "Monitor",
            "service_account_json": '{"type":"service_account","client_email":"bot@x.iam.gserviceaccount.com"}',
            "column_mapping": [
                {"field": "workflow_number", "header": "WF#", "order": 0},
                {"field": "step_name", "header": "Step", "order": 1},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["spreadsheet_id"] == "SPREADSHEET123"
    assert data["has_service_account"] is True
    assert "bot@x" not in (data.get("service_account_email_masked") or "") or "*" in (
        data.get("service_account_email_masked") or ""
    )
