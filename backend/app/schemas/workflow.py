"""Workflow-related schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TrackedWorkflowCreate(BaseModel):
    workflow_number: str = Field(min_length=1)
    notes: str = ""
    enabled: bool = True

    @field_validator("workflow_number")
    @classmethod
    def normalize_number(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("workflow_number is required")
        return v


class TrackedWorkflowBatchCreate(BaseModel):
    """Accept free text with numbers, ranges (800-850), and lists."""

    text: str = Field(min_length=1, description="Numbers, ranges like 800-850, comma/newline separated")
    enabled: bool = True
    prefix: str = "WF-"


class TrackedWorkflowUpdate(BaseModel):
    enabled: bool | None = None
    notes: str | None = None


class TrackedWorkflowOut(BaseModel):
    id: int
    workflow_number: str
    workflow_number_int: int | None = None
    enabled: bool
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkflowStepOut(BaseModel):
    id: int
    workflow_id: str
    workflow_number: str
    step_index: int | None = None
    step_name: str = ""
    step_status: str = ""
    step_outcome: str = ""
    participant: str = ""
    date_due: str = ""
    date_completed: str = ""
    date_in: str = ""
    overdue: str = ""
    final_mail_comment: str = ""
    sheet_sync_status: str = "pending"
    sheet_sync_error: str = ""
    last_synced_to_sheet_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkflowOut(BaseModel):
    id: int
    workflow_id: str
    workflow_number: str
    workflow_number_int: int | None = None
    workflow_title: str = ""
    review_status: str = ""
    review_outcome: str = ""
    is_completed: bool = False
    is_current: bool = True
    last_checked_at: datetime | None = None
    last_changed_at: datetime | None = None
    source: str = ""
    steps: list[WorkflowStepOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WorkflowHistoryOut(BaseModel):
    id: int
    workflow_id: str
    workflow_number: str
    step_index: int | None = None
    step_name: str = ""
    change_type: str = ""
    change_summary: str = ""
    old_data_json: str = ""
    new_data_json: str = ""
    checked_at: datetime

    model_config = {"from_attributes": True}


class WorkflowCommentOut(BaseModel):
    id: int
    workflow_number: str
    mail_id: str
    mail_subject: str = ""
    sent_date: str = ""
    from_user: str = ""
    comment_text: str = ""
    review_step: str = ""
    participant: str = ""
    review_outcome: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FeedbackRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    step_selector: str = "all"  # all | by_index | by_name
    step_indexes: list[int] = Field(default_factory=list)
    step_names: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(
        default_factory=lambda: [
            "workflow_number",
            "workflow_title",
            "step_name",
            "step_status",
            "step_outcome",
            "participant",
            "date_due",
            "date_completed",
            "overdue",
            "final_mail_comment",
        ]
    )
    status_filter: list[str] = Field(
        default_factory=lambda: ["Pending", "A", "B", "C", "Completed", "Terminated"]
    )
    triggers: list[str] = Field(
        default_factory=lambda: ["always", "data_changed", "pending_to_final"]
    )
    fetch_final_mail: bool = True
    priority: int = 100
    notes: str = ""

    @field_validator("step_selector")
    @classmethod
    def validate_selector(cls, v: str) -> str:
        if v not in {"all", "by_index", "by_name"}:
            raise ValueError("step_selector must be all, by_index, or by_name")
        return v


class FeedbackRuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    step_selector: str | None = None
    step_indexes: list[int] | None = None
    step_names: list[str] | None = None
    output_fields: list[str] | None = None
    status_filter: list[str] | None = None
    triggers: list[str] | None = None
    fetch_final_mail: bool | None = None
    priority: int | None = None
    notes: str | None = None


class FeedbackRuleOut(BaseModel):
    id: int
    name: str
    enabled: bool
    step_selector: str
    step_indexes: list[int] = Field(default_factory=list)
    step_names: list[str] = Field(default_factory=list)
    output_fields: list[str] = Field(default_factory=list)
    status_filter: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    fetch_final_mail: bool = True
    priority: int = 100
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TrackingModeUpdate(BaseModel):
    """Global tracking mode: tracked_only or auto_discover_current."""

    mode: str = Field(description="tracked_only | auto_discover_current")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in {"tracked_only", "auto_discover_current"}:
            raise ValueError("mode must be tracked_only or auto_discover_current")
        return v
