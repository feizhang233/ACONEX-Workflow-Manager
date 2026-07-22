"""Feedback rule evaluation."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import FeedbackRule, WorkflowHistory, WorkflowStep, utc_now
from app.services.aconex.xml_utils import review_code


AVAILABLE_OUTPUT_FIELDS = [
    "workflow_number",
    "workflow_title",
    "step_index",
    "step_name",
    "step_status",
    "step_outcome",
    "participant",
    "date_due",
    "date_completed",
    "overdue",
    "final_mail_comment",
    "review_status",
    "review_outcome",
]

AVAILABLE_TRIGGERS = [
    "always",
    "data_changed",
    "pending_to_final",
    "overdue",
    "workflow_completed",
]


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def rule_to_dict(rule: FeedbackRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "step_selector": rule.step_selector,
        "step_indexes": _loads(rule.step_indexes_json, []),
        "step_names": _loads(rule.step_names_json, []),
        "output_fields": _loads(rule.output_fields_json, []),
        "status_filter": _loads(rule.status_filter_json, []),
        "triggers": _loads(rule.triggers_json, []),
        "fetch_final_mail": rule.fetch_final_mail,
        "priority": rule.priority,
        "notes": rule.notes or "",
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def create_rule(db: Session, data: dict[str, Any]) -> FeedbackRule:
    rule = FeedbackRule(
        name=data["name"],
        enabled=data.get("enabled", True),
        step_selector=data.get("step_selector", "all"),
        step_indexes_json=json.dumps(data.get("step_indexes") or []),
        step_names_json=json.dumps(data.get("step_names") or []),
        output_fields_json=json.dumps(data.get("output_fields") or AVAILABLE_OUTPUT_FIELDS),
        status_filter_json=json.dumps(
            data.get("status_filter") or ["Pending", "A", "B", "C", "Completed", "Terminated"]
        ),
        triggers_json=json.dumps(data.get("triggers") or ["always", "data_changed"]),
        fetch_final_mail=data.get("fetch_final_mail", True),
        priority=data.get("priority", 100),
        notes=data.get("notes") or "",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule_id: int, data: dict[str, Any]) -> FeedbackRule | None:
    rule = db.query(FeedbackRule).filter(FeedbackRule.id == rule_id).first()
    if not rule:
        return None
    if "name" in data and data["name"] is not None:
        rule.name = data["name"]
    if "enabled" in data and data["enabled"] is not None:
        rule.enabled = data["enabled"]
    if "step_selector" in data and data["step_selector"] is not None:
        rule.step_selector = data["step_selector"]
    if "step_indexes" in data and data["step_indexes"] is not None:
        rule.step_indexes_json = json.dumps(data["step_indexes"])
    if "step_names" in data and data["step_names"] is not None:
        rule.step_names_json = json.dumps(data["step_names"])
    if "output_fields" in data and data["output_fields"] is not None:
        rule.output_fields_json = json.dumps(data["output_fields"])
    if "status_filter" in data and data["status_filter"] is not None:
        rule.status_filter_json = json.dumps(data["status_filter"])
    if "triggers" in data and data["triggers"] is not None:
        rule.triggers_json = json.dumps(data["triggers"])
    if "fetch_final_mail" in data and data["fetch_final_mail"] is not None:
        rule.fetch_final_mail = data["fetch_final_mail"]
    if "priority" in data and data["priority"] is not None:
        rule.priority = data["priority"]
    if "notes" in data and data["notes"] is not None:
        rule.notes = data["notes"]
    rule.updated_at = utc_now()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> bool:
    rule = db.query(FeedbackRule).filter(FeedbackRule.id == rule_id).first()
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def list_rules(db: Session) -> list[FeedbackRule]:
    return db.query(FeedbackRule).order_by(FeedbackRule.priority, FeedbackRule.id).all()


def get_enabled_rules(db: Session) -> list[FeedbackRule]:
    return (
        db.query(FeedbackRule)
        .filter(FeedbackRule.enabled.is_(True))
        .order_by(FeedbackRule.priority, FeedbackRule.id)
        .all()
    )


def ensure_default_rule(db: Session) -> FeedbackRule:
    existing = db.query(FeedbackRule).first()
    if existing:
        return existing
    return create_rule(
        db,
        {
            "name": "Default – all steps",
            "enabled": True,
            "step_selector": "all",
            "step_indexes": [],
            "step_names": [],
            "output_fields": AVAILABLE_OUTPUT_FIELDS,
            "status_filter": ["Pending", "A", "B", "C", "Completed", "Terminated"],
            "triggers": ["always", "data_changed", "pending_to_final"],
            "fetch_final_mail": True,
            "priority": 100,
            "notes": "Auto-created default rule",
        },
    )


def rule_matches_step(rule: FeedbackRule, step: WorkflowStep) -> bool:
    selector = rule.step_selector or "all"
    if selector == "all":
        return True
    if selector == "by_index":
        indexes = set(_loads(rule.step_indexes_json, []))
        return step.step_index in indexes if step.step_index is not None else False
    if selector == "by_name":
        names = {str(n).strip().lower() for n in _loads(rule.step_names_json, [])}
        return (step.step_name or "").strip().lower() in names
    return True


def status_allowed(rule: FeedbackRule, step: WorkflowStep) -> bool:
    filters = [str(s).strip().lower() for s in _loads(rule.status_filter_json, [])]
    if not filters:
        return True
    candidates = {
        (step.step_status or "").strip().lower(),
        (step.step_outcome or "").strip().lower(),
        review_code(step.step_outcome or step.step_status).lower(),
    }
    # Map common codes
    expanded = set(filters)
    for f in list(filters):
        if f in {"a", "b", "c"}:
            expanded.add(f)
        if f == "pending":
            expanded.update({"pending", "p", "pending action"})
        if f in {"completed", "terminated", "terminate"}:
            expanded.update({"completed", "terminated", "terminate", "closed"})
    return any(c in expanded for c in candidates if c)


def rule_wants_final_mail(rule: FeedbackRule) -> bool:
    return bool(rule.fetch_final_mail)


def step_triggered_for_mail(rule: FeedbackRule, step: WorkflowStep, db: Session) -> bool:
    triggers = set(_loads(rule.triggers_json, []))
    if "always" in triggers:
        code = review_code(step.step_outcome or step.step_status)
        return code in {"A", "B", "C"} or bool(step.date_completed)
    if "pending_to_final" in triggers:
        code = review_code(step.step_outcome or step.step_status)
        if code in {"A", "B", "C"} and not step.final_mail_comment:
            return True
        # Check history for recent pending→final
        history = (
            db.query(WorkflowHistory)
            .filter(
                WorkflowHistory.workflow_number == step.workflow_number,
                WorkflowHistory.step_index == step.step_index,
                WorkflowHistory.change_type == "status",
            )
            .order_by(WorkflowHistory.id.desc())
            .limit(5)
            .all()
        )
        for h in history:
            if "Pending→Final" in (h.change_summary or ""):
                return True
    if "data_changed" in triggers and step.sheet_sync_status == "pending":
        code = review_code(step.step_outcome or step.step_status)
        if code in {"A", "B", "C"}:
            return True
    if "overdue" in triggers and (step.overdue or "").lower() not in {"", "pending"}:
        return True
    if "workflow_completed" in triggers and step.date_completed:
        return True
    return False


def step_should_sync(rule: FeedbackRule, step: WorkflowStep, *, force: bool = False) -> bool:
    if not rule_matches_step(rule, step):
        return False
    if not status_allowed(rule, step):
        return False
    triggers = set(_loads(rule.triggers_json, []))
    if force or "always" in triggers:
        return True
    if "data_changed" in triggers and step.sheet_sync_status in {"pending", "failed"}:
        return True
    if "pending_to_final" in triggers:
        code = review_code(step.step_outcome or step.step_status)
        if code in {"A", "B", "C"} and step.sheet_sync_status in {"pending", "failed"}:
            return True
    if "overdue" in triggers and step.overdue and step.overdue.lower() != "pending":
        return True
    if "workflow_completed" in triggers and step.date_completed:
        return True
    return step.sheet_sync_status in {"pending", "failed"}


def collect_sync_rows(db: Session, *, force_all: bool = False) -> list[dict[str, Any]]:
    """Build row dicts for Google Sheets based on feedback rules."""
    rules = get_enabled_rules(db)
    if not rules:
        rules = [ensure_default_rule(db)]
    steps = db.query(WorkflowStep).all()
    # Map workflow metadata
    from app.models.entities import Workflow

    wf_map = {w.workflow_number: w for w in db.query(Workflow).all()}
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for step in steps:
        for rule in rules:
            if not step_should_sync(rule, step, force=force_all):
                continue
            fields = _loads(rule.output_fields_json, AVAILABLE_OUTPUT_FIELDS)
            wf = wf_map.get(step.workflow_number)
            row: dict[str, Any] = {}
            for field in fields:
                row[field] = _field_value(field, step, wf)
            # Always include business key fields
            row["workflow_number"] = step.workflow_number
            row["step_index"] = step.step_index
            row["step_name"] = step.step_name
            row["_step_id"] = step.id
            row["_rule_id"] = rule.id
            key = f"{step.workflow_number}|{step.step_index}|{step.step_name}"
            if key in seen_keys:
                break
            seen_keys.add(key)
            rows.append(row)
            break  # first matching rule wins (by priority)
    return rows


def _field_value(field: str, step: WorkflowStep, wf: Any) -> Any:
    mapping = {
        "workflow_number": step.workflow_number,
        "workflow_title": getattr(wf, "workflow_title", "") if wf else "",
        "step_index": step.step_index,
        "step_name": step.step_name,
        "step_status": step.step_status,
        "step_outcome": step.step_outcome,
        "participant": step.participant,
        "date_due": step.date_due,
        "date_completed": step.date_completed,
        "overdue": step.overdue,
        "final_mail_comment": step.final_mail_comment,
        "review_status": getattr(wf, "review_status", "") if wf else "",
        "review_outcome": getattr(wf, "review_outcome", "") if wf else "",
    }
    return mapping.get(field, "")
