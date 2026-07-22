"""Pytest fixtures with isolated SQLite DB and mocked external APIs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure encryption key before app import
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("ENCRYPTION_KEY", "")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.database import Base, get_db
from app.main import create_app
from app import models  # noqa: F401


@pytest.fixture()
def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine, monkeypatch):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    # Point all service-layer SessionLocal usage at the test DB
    monkeypatch.setattr("app.database.SessionLocal", Session)
    monkeypatch.setattr("app.services.pipeline.SessionLocal", Session)
    monkeypatch.setattr("app.services.run_service.SessionLocal", Session)
    monkeypatch.setattr("app.services.scheduler_service.SessionLocal", Session)
    monkeypatch.setattr("app.database.engine", db_engine)

    # Prevent scheduler side effects
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.shutdown_scheduler", lambda: None)
    monkeypatch.setattr("app.services.scheduler_service.register_job", lambda job: None)
    monkeypatch.setattr("app.services.scheduler_service.unregister_job", lambda job_id: None)
    monkeypatch.setattr("app.services.scheduler_service.reload_jobs_from_db", lambda: None)

    # Avoid init_db writing to the real default path during lifespan
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr(
        "app.main.session_scope",
        lambda: _session_scope_factory(Session),
    )

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


from contextlib import contextmanager


@contextmanager
def _session_scope_factory(Session):
    db = Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SAMPLE_WORKFLOW_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Workflows TotalPages="1" PageNumber="1">
  <Workflow WorkflowId="W100">
    <WorkflowNumber>WF-800</WorkflowNumber>
    <WorkflowName>Test Drawing Review</WorkflowName>
    <WorkflowStatus>In Progress</WorkflowStatus>
    <StepName>Step 1</StepName>
    <StepStatus>Completed</StepStatus>
    <StepOutcome>A</StepOutcome>
    <DateCompleted>2026-01-10T10:00:00Z</DateCompleted>
    <DateDue>2026-01-09T10:00:00Z</DateDue>
    <Participant>Alice</Participant>
  </Workflow>
  <Workflow WorkflowId="W100">
    <WorkflowNumber>WF-800</WorkflowNumber>
    <WorkflowName>Test Drawing Review</WorkflowName>
    <WorkflowStatus>In Progress</WorkflowStatus>
    <StepName>Step 2</StepName>
    <StepStatus>Pending</StepStatus>
    <StepOutcome></StepOutcome>
    <DateDue>2026-01-20T10:00:00Z</DateDue>
    <Participant>Bob</Participant>
  </Workflow>
  <Workflow WorkflowId="W101">
    <WorkflowNumber>WF-801</WorkflowNumber>
    <WorkflowName>Another WF</WorkflowName>
    <WorkflowStatus>Completed</WorkflowStatus>
    <StepName>Step 1</StepName>
    <StepStatus>Completed</StepStatus>
    <StepOutcome>B</StepOutcome>
    <DateCompleted>2026-01-12T10:00:00Z</DateCompleted>
  </Workflow>
</Workflows>
"""

SAMPLE_MAIL_LIST_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<MailSearch TotalPages="1">
  <Mail MailId="M1" MailNo="MAIL-1">
    <Subject>Final (WF-800)</Subject>
    <SentDate>2026-01-11T12:00:00Z</SentDate>
    <FromUserDetails><FullName>Reviewer</FullName></FromUserDetails>
  </Mail>
</MailSearch>
"""

SAMPLE_MAIL_DETAIL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Mail MailId="M1">
  <Subject>Final (WF-800)</Subject>
  <MailBody>Looks good with minor notes.</MailBody>
</Mail>
"""
