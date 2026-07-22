"""Job / run schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


SCHEDULE_TYPES = {"interval_minutes", "interval_hours", "daily", "weekly", "cron"}
JOB_TYPES = {
    "pipeline",
    "sync_tracked",
    "sync_current",
    "fetch_comments",
    "sync_sheets",
}


def _validate_daily_time(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError("daily_time must use HH:MM with a valid 24-hour time") from exc
    return value


def _validate_weekdays(value: list[int] | None) -> list[int] | None:
    if value is not None and any(day < 0 or day > 6 for day in value):
        raise ValueError("weekdays must contain values from 0 (Monday) to 6 (Sunday)")
    return value


def _validate_cron(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value.split()) != 5:
        raise ValueError("cron_expression must contain 5 fields")
    return value


class ScheduledJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    schedule_type: str = "interval_minutes"
    interval_value: int | None = Field(default=None, ge=1)
    daily_time: str | None = None  # HH:MM
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    cron_expression: str | None = None
    timezone: str = "Europe/Belgrade"
    job_type: str = "pipeline"
    job_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: str) -> str:
        if v not in SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of {SCHEDULE_TYPES}")
        return v

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return v

    _daily_time = field_validator("daily_time")(_validate_daily_time)
    _weekdays = field_validator("weekdays")(_validate_weekdays)
    _cron_expression = field_validator("cron_expression")(_validate_cron)


class ScheduledJobUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    schedule_type: str | None = None
    interval_value: int | None = Field(default=None, ge=1)
    daily_time: str | None = None
    weekdays: list[int] | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    job_type: str | None = None
    job_params: dict[str, Any] | None = None

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: str | None) -> str | None:
        if v is not None and v not in SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of {SCHEDULE_TYPES}")
        return v

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str | None) -> str | None:
        if v is not None and v not in JOB_TYPES:
            raise ValueError(f"job_type must be one of {JOB_TYPES}")
        return v

    _daily_time = field_validator("daily_time")(_validate_daily_time)
    _weekdays = field_validator("weekdays")(_validate_weekdays)
    _cron_expression = field_validator("cron_expression")(_validate_cron)


class ScheduledJobOut(BaseModel):
    id: int
    name: str
    enabled: bool
    schedule_type: str
    interval_value: int | None = None
    daily_time: str | None = None
    weekdays: list[int] = Field(default_factory=list)
    cron_expression: str | None = None
    timezone: str = "Europe/Belgrade"
    job_type: str
    job_params: dict[str, Any] = Field(default_factory=dict)
    last_run_at: datetime | None = None
    last_run_status: str = ""
    next_run_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ManualRunRequest(BaseModel):
    action: str = Field(
        description="pipeline | sync_tracked | sync_current | fetch_comments | sync_sheets"
    )
    workflow_numbers: list[str] | None = None
    full_sheet_sync: bool = False
    max_pages: int | None = Field(default=None, ge=1, le=500)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {
            "pipeline",
            "sync_tracked",
            "sync_current",
            "fetch_comments",
            "sync_sheets",
        }
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


class RunLogOut(BaseModel):
    id: int
    timestamp: datetime
    level: str
    stage: str
    message: str

    model_config = {"from_attributes": True}


class UpdateRunOut(BaseModel):
    id: int
    command: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    checked_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    sheet_synced_count: int = 0
    progress_pct: float = 0.0
    current_stage: str = ""
    error_message: str = ""
    notes: str = ""
    triggered_by: str = "manual"
    scheduled_job_id: int | None = None
    parent_run_id: int | None = None
    logs: list[RunLogOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    tracked_count: int = 0
    tracked_enabled: int = 0
    workflow_count: int = 0
    current_count: int = 0
    pending_sheet_sync: int = 0
    failed_sheet_sync: int = 0
    last_run: UpdateRunOut | None = None
    active_run: UpdateRunOut | None = None
    aconex_configured: bool = False
    sheets_configured: bool = False
    scheduled_jobs_enabled: int = 0
