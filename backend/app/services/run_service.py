"""Update run lifecycle, logging, and SSE-friendly progress."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.entities import RunLog, UpdateRun, utc_now


# In-process subscribers: run_id -> list of queues/callbacks
_subscribers: dict[int, list[Callable[[dict[str, Any]], None]]] = {}
_sub_lock = threading.Lock()


def subscribe(run_id: int, callback: Callable[[dict[str, Any]], None]) -> None:
    with _sub_lock:
        _subscribers.setdefault(run_id, []).append(callback)


def unsubscribe(run_id: int, callback: Callable[[dict[str, Any]], None]) -> None:
    with _sub_lock:
        subs = _subscribers.get(run_id, [])
        if callback in subs:
            subs.remove(callback)
        if not subs and run_id in _subscribers:
            del _subscribers[run_id]


def _publish(run_id: int, event: dict[str, Any]) -> None:
    with _sub_lock:
        subs = list(_subscribers.get(run_id, []))
    for cb in subs:
        try:
            cb(event)
        except Exception:
            pass


def create_run(
    db: Session,
    command: str,
    *,
    triggered_by: str = "manual",
    scheduled_job_id: int | None = None,
    parent_run_id: int | None = None,
    notes: str = "",
) -> UpdateRun:
    run = UpdateRun(
        command=command,
        status="running",
        triggered_by=triggered_by,
        scheduled_job_id=scheduled_job_id,
        parent_run_id=parent_run_id,
        notes=notes,
        current_stage="starting",
        progress_pct=0.0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    append_log(db, run.id, "INFO", "starting", f"Run started: {command}")
    return run


def append_log(
    db: Session,
    run_id: int,
    level: str,
    stage: str,
    message: str,
) -> RunLog:
    log = RunLog(run_id=run_id, level=level, stage=stage, message=message)
    db.add(log)
    run = db.query(UpdateRun).filter(UpdateRun.id == run_id).first()
    if run and stage:
        run.current_stage = stage
        db.add(run)
    db.commit()
    db.refresh(log)
    _publish(
        run_id,
        {
            "type": "log",
            "run_id": run_id,
            "level": level,
            "stage": stage,
            "message": message,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        },
    )
    return log


def update_progress(
    db: Session,
    run_id: int,
    *,
    progress_pct: float | None = None,
    stage: str | None = None,
    checked_count: int | None = None,
    updated_count: int | None = None,
    failed_count: int | None = None,
    sheet_synced_count: int | None = None,
) -> None:
    run = db.query(UpdateRun).filter(UpdateRun.id == run_id).first()
    if not run:
        return
    if progress_pct is not None:
        run.progress_pct = max(0.0, min(100.0, progress_pct))
    if stage is not None:
        run.current_stage = stage
    if checked_count is not None:
        run.checked_count = checked_count
    if updated_count is not None:
        run.updated_count = updated_count
    if failed_count is not None:
        run.failed_count = failed_count
    if sheet_synced_count is not None:
        run.sheet_synced_count = sheet_synced_count
    db.add(run)
    db.commit()
    _publish(
        run_id,
        {
            "type": "progress",
            "run_id": run_id,
            "progress_pct": run.progress_pct,
            "stage": run.current_stage,
            "checked_count": run.checked_count,
            "updated_count": run.updated_count,
            "failed_count": run.failed_count,
            "sheet_synced_count": run.sheet_synced_count,
            "status": run.status,
        },
    )


def finish_run(
    db: Session,
    run_id: int,
    *,
    status: str = "success",
    error_message: str = "",
) -> UpdateRun | None:
    run = db.query(UpdateRun).filter(UpdateRun.id == run_id).first()
    if not run:
        return None
    run.status = status
    run.finished_at = utc_now()
    run.progress_pct = 100.0 if status == "success" else run.progress_pct
    run.error_message = error_message or ""
    if status == "success" and not run.current_stage:
        run.current_stage = "done"
    db.add(run)
    db.commit()
    db.refresh(run)
    append_log(
        db,
        run_id,
        "INFO" if status == "success" else "ERROR",
        "done",
        f"Run finished with status={status}" + (f": {error_message}" if error_message else ""),
    )
    _publish(
        run_id,
        {
            "type": "finished",
            "run_id": run_id,
            "status": status,
            "error_message": error_message,
            "checked_count": run.checked_count,
            "updated_count": run.updated_count,
            "failed_count": run.failed_count,
            "sheet_synced_count": run.sheet_synced_count,
        },
    )
    return run


def get_run(db: Session, run_id: int, *, with_logs: bool = True) -> UpdateRun | None:
    q = db.query(UpdateRun)
    if with_logs:
        q = q.options(joinedload(UpdateRun.logs))
    return q.filter(UpdateRun.id == run_id).first()


def list_runs(db: Session, *, limit: int = 50, offset: int = 0) -> tuple[list[UpdateRun], int]:
    total = db.query(UpdateRun).count()
    items = (
        db.query(UpdateRun)
        .order_by(UpdateRun.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def get_active_run(db: Session) -> UpdateRun | None:
    return (
        db.query(UpdateRun)
        .filter(UpdateRun.status == "running")
        .order_by(UpdateRun.id.desc())
        .first()
    )


def make_run_logger(db: Session, run_id: int) -> Callable[[str, str, str], None]:
    def log(level: str, stage: str, message: str) -> None:
        append_log(db, run_id, level, stage, message)

    return log


def run_in_background(fn: Callable[[], None]) -> None:
    thread = threading.Thread(target=fn, daemon=True)
    thread.start()
