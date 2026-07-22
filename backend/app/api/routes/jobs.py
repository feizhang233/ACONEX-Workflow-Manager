"""Scheduled jobs, manual runs, history, SSE."""

from __future__ import annotations

import asyncio
import json
import queue
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import SyncQueueItem, Workflow, WorkflowStep
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.jobs import (
    DashboardStats,
    ManualRunRequest,
    ScheduledJobCreate,
    ScheduledJobOut,
    ScheduledJobUpdate,
    UpdateRunOut,
)
from app.services.aconex.auth import AconexAuthService
from app.services import google_sheets_service as gsheets
from app.services import scheduler_service
from app.services.pipeline import JobConflictError, start_manual_run
from app.services.run_service import get_active_run, get_run, list_runs, subscribe, unsubscribe
from app.services.workflow_service import list_tracked

router = APIRouter(tags=["jobs"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    tracked = list_tracked(db)
    auth = AconexAuthService(db)
    sheets = gsheets.public_settings(db)
    last_items, _ = list_runs(db, limit=1)
    last_run = last_items[0] if last_items else None
    active = get_active_run(db)
    jobs = db.query(scheduler_service.ScheduledJob).filter_by(enabled=True).count() if False else 0
    from app.models.entities import ScheduledJob

    jobs = db.query(ScheduledJob).filter(ScheduledJob.enabled.is_(True)).count()
    return DashboardStats(
        tracked_count=len(tracked),
        tracked_enabled=sum(1 for t in tracked if t.enabled),
        workflow_count=db.query(Workflow).count(),
        current_count=db.query(Workflow).filter(Workflow.is_completed.is_(False)).count(),
        pending_sheet_sync=db.query(WorkflowStep)
        .filter(WorkflowStep.sheet_sync_status == "pending")
        .count(),
        failed_sheet_sync=db.query(WorkflowStep)
        .filter(WorkflowStep.sheet_sync_status == "failed")
        .count(),
        last_run=UpdateRunOut.model_validate(last_run) if last_run else None,
        active_run=UpdateRunOut.model_validate(active) if active else None,
        aconex_configured=bool(auth.row.client_id and (auth.refresh_token or auth.access_token)),
        sheets_configured=bool(sheets.get("spreadsheet_id") and sheets.get("has_service_account")),
        scheduled_jobs_enabled=jobs,
    )


@router.get("/scheduled-jobs", response_model=list[ScheduledJobOut])
def list_jobs(db: Session = Depends(get_db)):
    from app.models.entities import ScheduledJob

    jobs = db.query(ScheduledJob).order_by(ScheduledJob.id).all()
    return [ScheduledJobOut(**scheduler_service.job_to_dict(j)) for j in jobs]


@router.post("/scheduled-jobs", response_model=ScheduledJobOut)
def create_job(body: ScheduledJobCreate, db: Session = Depends(get_db)):
    try:
        job = scheduler_service.create_scheduled_job(db, body.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduledJobOut(**scheduler_service.job_to_dict(job))


@router.put("/scheduled-jobs/{job_id}", response_model=ScheduledJobOut)
def update_job(job_id: int, body: ScheduledJobUpdate, db: Session = Depends(get_db)):
    try:
        job = scheduler_service.update_scheduled_job(db, job_id, body.model_dump(exclude_unset=True))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ScheduledJobOut(**scheduler_service.job_to_dict(job))


@router.delete("/scheduled-jobs/{job_id}", response_model=MessageResponse)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    if not scheduler_service.delete_scheduled_job(db, job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return MessageResponse(message="Deleted")


@router.post("/scheduled-jobs/{job_id}/run", response_model=dict)
def run_job_now(job_id: int, db: Session = Depends(get_db)):
    from app.models.entities import ScheduledJob

    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        params = json.loads(job.job_params_json or "{}")
    except json.JSONDecodeError:
        params = {}
    try:
        run_id = start_manual_run(
            action=job.job_type or "pipeline",
            workflow_numbers=params.get("workflow_numbers"),
            full_sheet_sync=bool(params.get("full_sheet_sync", False)),
            max_pages=params.get("max_pages"),
            triggered_by="manual",
            scheduled_job_id=job_id,
        )
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run_id, "message": "Job started"}


@router.post("/runs", response_model=dict)
def start_run(body: ManualRunRequest, db: Session = Depends(get_db)):
    try:
        run_id = start_manual_run(
            action=body.action,
            workflow_numbers=body.workflow_numbers,
            full_sheet_sync=body.full_sheet_sync,
            max_pages=body.max_pages,
            triggered_by="manual",
        )
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run_id, "message": f"Started {body.action}"}


@router.get("/runs", response_model=PaginatedResponse[UpdateRunOut])
def get_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = list_runs(db, limit=page_size, offset=(page - 1) * page_size)
    return PaginatedResponse(
        items=[UpdateRunOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/runs/{run_id}", response_model=UpdateRunOut)
def get_one_run(run_id: int, db: Session = Depends(get_db)):
    run = get_run(db, run_id, with_logs=True)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return UpdateRunOut.model_validate(run)


@router.post("/runs/{run_id}/retry", response_model=dict)
def retry_run(run_id: int, db: Session = Depends(get_db)):
    run = get_run(db, run_id, with_logs=False)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "running":
        raise HTTPException(status_code=409, detail="Run is still running")
    try:
        new_id = start_manual_run(
            action=run.command,
            triggered_by="retry",
            parent_run_id=run.id,
            scheduled_job_id=run.scheduled_job_id,
        )
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": new_id, "message": "Retry started"}


@router.get("/runs/{run_id}/events")
async def run_events(run_id: int, db: Session = Depends(get_db)):
    run = get_run(db, run_id, with_logs=True)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    q: queue.Queue[dict[str, Any] | None] = queue.Queue()

    def _callback(event: dict[str, Any]) -> None:
        q.put(event)

    subscribe(run_id, _callback)

    async def event_generator():
        try:
            # Send snapshot
            snapshot = {
                "type": "snapshot",
                "run_id": run_id,
                "status": run.status,
                "progress_pct": run.progress_pct,
                "stage": run.current_stage,
                "logs": [
                    {
                        "level": log.level,
                        "stage": log.stage,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    }
                    for log in (run.logs or [])
                ],
            }
            yield f"data: {json.dumps(snapshot, default=str)}\n\n"
            if run.status != "running":
                yield f"data: {json.dumps({'type': 'finished', 'run_id': run_id, 'status': run.status})}\n\n"
                return
            while True:
                try:
                    event = await asyncio.get_event_loop().run_in_executor(None, lambda: q.get(timeout=15))
                except Exception:
                    # keepalive
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    # re-check DB status
                    from app.database import SessionLocal

                    s = SessionLocal()
                    try:
                        current = get_run(s, run_id, with_logs=False)
                        if current and current.status != "running":
                            yield f"data: {json.dumps({'type': 'finished', 'run_id': run_id, 'status': current.status})}\n\n"
                            break
                    finally:
                        s.close()
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "finished":
                    break
        finally:
            unsubscribe(run_id, _callback)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
