"""SQLAlchemy entity models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AconexSettings(Base):
    __tablename__ = "aconex_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    authorization_url: Mapped[str] = mapped_column(String(512), default="")
    token_url: Mapped[str] = mapped_column(String(512), default="")
    base_url: Mapped[str] = mapped_column(String(512), default="https://eu1.aconex.com")
    api_audience: Mapped[str] = mapped_column(String(512), default="https://api.aconex.com")
    client_id: Mapped[str] = mapped_column(String(256), default="")
    client_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_uri: Mapped[str] = mapped_column(String(512), default="http://localhost:8080/callback")
    authorization_state: Mapped[str] = mapped_column(String(128), default="aconex-local-auth")
    token_auth_method: Mapped[str] = mapped_column(String(16), default="basic")
    project_id: Mapped[str] = mapped_column(String(64), default="")
    project_name: Mapped[str] = mapped_column(String(256), default="")
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    default_mail_box: Mapped[str] = mapped_column(String(64), default="inbox")
    page_size: Mapped[int] = mapped_column(Integer, default=250)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class GoogleSheetsSettings(Base):
    __tablename__ = "google_sheets_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    spreadsheet_id: Mapped[str] = mapped_column(String(256), default="")
    sheet_name: Mapped[str] = mapped_column(String(128), default="Workflow Monitor")
    service_account_json_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list of {field, header, order}
    column_mapping_json: Mapped[str] = mapped_column(
        Text,
        default=(
            '[{"field":"workflow_number","header":"Workflow Number","order":0},'
            '{"field":"workflow_title","header":"Workflow Title","order":1},'
            '{"field":"step_name","header":"Step","order":2},'
            '{"field":"step_status","header":"Status","order":3},'
            '{"field":"step_outcome","header":"Outcome","order":4},'
            '{"field":"participant","header":"Participant","order":5},'
            '{"field":"date_due","header":"Due Date","order":6},'
            '{"field":"date_completed","header":"Completed Date","order":7},'
            '{"field":"overdue","header":"Overdue","order":8},'
            '{"field":"final_mail_comment","header":"Final Mail Comment","order":9}]'
        ),
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class TrackedWorkflow(Base):
    """User-managed tracking list (numbers to watch)."""

    __tablename__ = "tracked_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    workflow_number_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    workflow_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_number_int: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    workflow_title: Mapped[str] = mapped_column(String(512), default="")
    review_status: Mapped[str] = mapped_column(String(64), default="")
    review_outcome: Mapped[str] = mapped_column(String(64), default="")
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    raw_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    steps: Mapped[list[WorkflowStep]] = relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan"
    )
    history: Mapped[list[WorkflowHistory]] = relationship(
        "WorkflowHistory", back_populates="workflow", cascade="all, delete-orphan"
    )
    comments: Mapped[list[WorkflowComment]] = relationship(
        "WorkflowComment", back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_index", "step_name", name="uq_workflow_step"),
        Index("ix_workflow_steps_number_step", "workflow_number", "step_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_pk: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), index=True)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_number: Mapped[str] = mapped_column(String(64), nullable=False)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_name: Mapped[str] = mapped_column(String(256), default="")
    step_status: Mapped[str] = mapped_column(String(64), default="")
    step_outcome: Mapped[str] = mapped_column(String(64), default="")
    participant: Mapped[str] = mapped_column(String(256), default="")
    date_due: Mapped[str] = mapped_column(String(64), default="")
    date_completed: Mapped[str] = mapped_column(String(64), default="")
    date_in: Mapped[str] = mapped_column(String(64), default="")
    overdue: Mapped[str] = mapped_column(String(128), default="")
    final_mail_comment: Mapped[str] = mapped_column(Text, default="")
    last_synced_to_sheet_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sheet_sync_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|synced|failed
    sheet_sync_error: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="steps")


class WorkflowHistory(Base):
    __tablename__ = "workflow_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_pk: Mapped[int | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    workflow_number: Mapped[str] = mapped_column(String(64), default="", index=True)
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_name: Mapped[str] = mapped_column(String(256), default="")
    change_type: Mapped[str] = mapped_column(String(64), default="status")  # status|new|comment
    change_summary: Mapped[str] = mapped_column(Text, default="")
    old_data_json: Mapped[str] = mapped_column(Text, default="")
    new_data_json: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    workflow: Mapped[Workflow | None] = relationship("Workflow", back_populates="history")


class WorkflowComment(Base):
    __tablename__ = "workflow_comments"
    __table_args__ = (
        UniqueConstraint("workflow_number", "mail_id", name="uq_workflow_comment_mail"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_pk: Mapped[int | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_number_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mail_id: Mapped[str] = mapped_column(String(128), nullable=False)
    mail_number: Mapped[str] = mapped_column(String(64), default="")
    mail_subject: Mapped[str] = mapped_column(String(512), default="")
    sent_date: Mapped[str] = mapped_column(String(64), default="")
    from_user: Mapped[str] = mapped_column(String(256), default="")
    comment_text: Mapped[str] = mapped_column(Text, default="")
    doc_no: Mapped[str] = mapped_column(String(128), default="")
    review_step: Mapped[str] = mapped_column(String(128), default="")
    participant: Mapped[str] = mapped_column(String(256), default="")
    review_outcome: Mapped[str] = mapped_column(String(64), default="")
    review_comment: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    workflow: Mapped[Workflow | None] = relationship("Workflow", back_populates="comments")


class FeedbackRule(Base):
    """Configurable rules for which steps/fields/triggers to process."""

    __tablename__ = "feedback_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # step_selector: all | by_index | by_name
    step_selector: Mapped[str] = mapped_column(String(32), default="all")
    step_indexes_json: Mapped[str] = mapped_column(Text, default="[]")  # e.g. [1,2]
    step_names_json: Mapped[str] = mapped_column(Text, default="[]")
    # fields to include in sync output
    output_fields_json: Mapped[str] = mapped_column(
        Text,
        default=(
            '["workflow_number","workflow_title","step_name","step_status","step_outcome",'
            '"participant","date_due","date_completed","overdue","final_mail_comment"]'
        ),
    )
    # statuses to sync: Pending, A, B, C, Completed, Terminated, etc.
    status_filter_json: Mapped[str] = mapped_column(
        Text,
        default='["Pending","A","B","C","Completed","Terminated"]',
    )
    # triggers: always | data_changed | pending_to_final | overdue | workflow_completed
    triggers_json: Mapped[str] = mapped_column(
        Text,
        default='["always","data_changed","pending_to_final"]',
    )
    fetch_final_mail: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # interval_minutes | interval_hours | daily | weekly | cron
    schedule_type: Mapped[str] = mapped_column(String(32), default="interval_minutes")
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes or hours
    daily_time: Mapped[str | None] = mapped_column(String(16), nullable=True)  # HH:MM
    weekdays_json: Mapped[str] = mapped_column(Text, default="[0,1,2,3,4]")  # mon-fri
    cron_expression: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Belgrade")
    # pipeline | sync_tracked | sync_current | fetch_comments | sync_sheets
    job_type: Mapped[str] = mapped_column(String(64), default="pipeline")
    job_params_json: Mapped[str] = mapped_column(Text, default="{}")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(32), default="")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class JobLock(Base):
    """Prevent concurrent execution of the same logical job."""

    __tablename__ = "job_locks"

    lock_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128), default="")
    acquired_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UpdateRun(Base):
    __tablename__ = "update_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|success|failed|cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checked_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    sheet_synced_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    current_stage: Mapped[str] = mapped_column(String(128), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    triggered_by: Mapped[str] = mapped_column(String(64), default="manual")  # manual|schedule|retry
    scheduled_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    logs: Mapped[list[RunLog]] = relationship(
        "RunLog", back_populates="run", cascade="all, delete-orphan", order_by="RunLog.id"
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("update_runs.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    level: Mapped[str] = mapped_column(String(16), default="INFO")
    stage: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[UpdateRun] = relationship("UpdateRun", back_populates="logs")


class SyncQueueItem(Base):
    """Pending Google Sheets sync rows (workflow_number + step)."""

    __tablename__ = "sync_queue"
    __table_args__ = (
        UniqueConstraint("workflow_number", "step_key", name="uq_sync_queue_biz_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_number: Mapped[str] = mapped_column(String(64), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)  # step_index or step_name
    step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_name: Mapped[str] = mapped_column(String(256), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|synced|failed
    error_message: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
