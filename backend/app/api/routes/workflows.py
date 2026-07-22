"""Workflow tracking and data routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.workflow import (
    FeedbackRuleCreate,
    FeedbackRuleOut,
    FeedbackRuleUpdate,
    TrackedWorkflowBatchCreate,
    TrackedWorkflowCreate,
    TrackedWorkflowOut,
    TrackedWorkflowUpdate,
    WorkflowCommentOut,
    WorkflowHistoryOut,
    WorkflowOut,
    WorkflowStepOut,
)
from app.services import feedback_service
from app.services.workflow_service import (
    add_tracked_numbers,
    delete_tracked,
    get_workflow_detail,
    list_comments,
    list_history,
    list_tracked,
    list_workflows,
    parse_workflow_number_input,
    set_tracked_enabled,
)

router = APIRouter(tags=["workflows"])


@router.get("/tracked-workflows", response_model=list[TrackedWorkflowOut])
def get_tracked(enabled_only: bool = False, db: Session = Depends(get_db)):
    return list_tracked(db, enabled_only=enabled_only)


@router.post("/tracked-workflows", response_model=TrackedWorkflowOut)
def create_tracked(body: TrackedWorkflowCreate, db: Session = Depends(get_db)):
    result = add_tracked_numbers(
        db, [body.workflow_number], enabled=body.enabled, notes=body.notes
    )
    items = result["items"]
    if not items:
        raise HTTPException(status_code=400, detail="Could not create tracked workflow")
    return items[0]


@router.post("/tracked-workflows/batch", response_model=dict)
def batch_tracked(body: TrackedWorkflowBatchCreate, db: Session = Depends(get_db)):
    try:
        numbers = parse_workflow_number_input(body.text, prefix=body.prefix)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not numbers:
        raise HTTPException(status_code=400, detail="No valid workflow numbers found")
    result = add_tracked_numbers(db, numbers, enabled=body.enabled)
    return {
        "created": result["created"],
        "skipped": result["skipped"],
        "total": len(numbers),
        "items": [TrackedWorkflowOut.model_validate(i) for i in result["items"]],
    }


@router.patch("/tracked-workflows/{tracked_id}", response_model=TrackedWorkflowOut)
def patch_tracked(tracked_id: int, body: TrackedWorkflowUpdate, db: Session = Depends(get_db)):
    if body.enabled is not None:
        row = set_tracked_enabled(db, tracked_id, body.enabled)
    else:
        from app.models.entities import TrackedWorkflow, utc_now

        row = db.query(TrackedWorkflow).filter(TrackedWorkflow.id == tracked_id).first()
        if row and body.notes is not None:
            row.notes = body.notes
            row.updated_at = utc_now()
            db.add(row)
            db.commit()
            db.refresh(row)
    if not row:
        raise HTTPException(status_code=404, detail="Tracked workflow not found")
    if body.notes is not None and body.enabled is not None:
        from app.models.entities import TrackedWorkflow, utc_now

        row = db.query(TrackedWorkflow).filter(TrackedWorkflow.id == tracked_id).first()
        if row:
            row.notes = body.notes
            row.updated_at = utc_now()
            db.add(row)
            db.commit()
            db.refresh(row)
    return row


@router.delete("/tracked-workflows/{tracked_id}", response_model=MessageResponse)
def remove_tracked(tracked_id: int, db: Session = Depends(get_db)):
    if not delete_tracked(db, tracked_id):
        raise HTTPException(status_code=404, detail="Tracked workflow not found")
    return MessageResponse(message="Deleted")


@router.get("/workflows", response_model=PaginatedResponse[WorkflowOut])
def get_workflows(
    q: str | None = None,
    current_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = list_workflows(db, q=q, current_only=current_only, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[WorkflowOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/workflows/{workflow_number}", response_model=WorkflowOut)
def get_one_workflow(workflow_number: str, db: Session = Depends(get_db)):
    wf = get_workflow_detail(db, workflow_number)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowOut.model_validate(wf)


@router.get("/workflows/{workflow_number}/history", response_model=list[WorkflowHistoryOut])
def get_history(workflow_number: str, limit: int = 100, db: Session = Depends(get_db)):
    return list_history(db, workflow_number=workflow_number, limit=limit)


@router.get("/workflows/{workflow_number}/comments", response_model=list[WorkflowCommentOut])
def get_comments(workflow_number: str, limit: int = 100, db: Session = Depends(get_db)):
    return list_comments(db, workflow_number=workflow_number, limit=limit)


@router.get("/history", response_model=list[WorkflowHistoryOut])
def get_all_history(limit: int = 100, db: Session = Depends(get_db)):
    return list_history(db, limit=limit)


@router.get("/comments", response_model=list[WorkflowCommentOut])
def get_all_comments(limit: int = 100, db: Session = Depends(get_db)):
    return list_comments(db, limit=limit)


@router.get("/steps", response_model=list[WorkflowStepOut])
def get_steps(
    workflow_number: str | None = None,
    sync_status: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    from app.models.entities import WorkflowStep

    q = db.query(WorkflowStep)
    if workflow_number:
        q = q.filter(WorkflowStep.workflow_number == workflow_number)
    if sync_status:
        q = q.filter(WorkflowStep.sheet_sync_status == sync_status)
    return q.order_by(WorkflowStep.workflow_number, WorkflowStep.step_index).limit(limit).all()


# Feedback rules
@router.get("/feedback-rules", response_model=list[FeedbackRuleOut])
def get_rules(db: Session = Depends(get_db)):
    feedback_service.ensure_default_rule(db)
    return [FeedbackRuleOut(**feedback_service.rule_to_dict(r)) for r in feedback_service.list_rules(db)]


@router.post("/feedback-rules", response_model=FeedbackRuleOut)
def create_rule(body: FeedbackRuleCreate, db: Session = Depends(get_db)):
    rule = feedback_service.create_rule(db, body.model_dump())
    return FeedbackRuleOut(**feedback_service.rule_to_dict(rule))


@router.put("/feedback-rules/{rule_id}", response_model=FeedbackRuleOut)
def update_rule(rule_id: int, body: FeedbackRuleUpdate, db: Session = Depends(get_db)):
    rule = feedback_service.update_rule(db, rule_id, body.model_dump(exclude_unset=True))
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return FeedbackRuleOut(**feedback_service.rule_to_dict(rule))


@router.delete("/feedback-rules/{rule_id}", response_model=MessageResponse)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    if not feedback_service.delete_rule(db, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return MessageResponse(message="Deleted")


@router.get("/feedback-rules/meta/fields")
def rule_meta():
    return {
        "output_fields": feedback_service.AVAILABLE_OUTPUT_FIELDS,
        "triggers": feedback_service.AVAILABLE_TRIGGERS,
        "step_selectors": ["all", "by_index", "by_name"],
        "status_options": ["Pending", "A", "B", "C", "Completed", "Terminated"],
    }
