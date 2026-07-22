"""Shared pipeline used by API and scheduled jobs."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.entities import JobLock, ScheduledJob, utc_now
from app.services.aconex.auth import AconexAuthService, AuthError
from app.services.aconex.client import AconexClient, AconexApiError
from app.services.google_sheets_service import GoogleSheetsError, sync_to_sheets
from app.services.mail_service import scan_final_mail
from app.services.run_service import (
    create_run,
    finish_run,
    make_run_logger,
    run_in_background,
    update_progress,
)
from app.services.workflow_service import sync_current_workflows, sync_tracked_workflows


class JobConflictError(RuntimeError):
    pass


def acquire_lock(db: Session, lock_key: str, *, owner: str, ttl_seconds: int = 3600) -> bool:
    from datetime import timedelta

    now = utc_now()
    existing = db.query(JobLock).filter(JobLock.lock_key == lock_key).first()
    if existing:
        if existing.expires_at and existing.expires_at > now:
            return False
        db.delete(existing)
        db.flush()
    lock = JobLock(
        lock_key=lock_key,
        owner=owner,
        acquired_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(lock)
    try:
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def release_lock(db: Session, lock_key: str) -> None:
    db.query(JobLock).filter(JobLock.lock_key == lock_key).delete()
    db.commit()


def execute_action(
    db: Session,
    action: str,
    *,
    run_id: int,
    workflow_numbers: list[str] | None = None,
    full_sheet_sync: bool = False,
    max_pages: int | None = None,
    client: AconexClient | None = None,
) -> dict[str, Any]:
    log = make_run_logger(db, run_id)
    owns_client = client is None
    result: dict[str, Any] = {
        "checked": 0,
        "updated": 0,
        "failed": 0,
        "sheet_synced": 0,
    }

    try:
        if action in {"pipeline", "sync_tracked", "sync_current", "fetch_comments"}:
            if client is None:
                auth = AconexAuthService(db)
                client = AconexClient(db, auth)

        if action == "sync_tracked":
            update_progress(db, run_id, progress_pct=10, stage="sync_tracked")
            counts = sync_tracked_workflows(
                db, client, workflow_numbers=workflow_numbers, max_pages=max_pages, log=log
            )
            result["checked"] += counts.get("checked", 0)
            result["updated"] += counts.get("updated", 0)

        elif action == "sync_current":
            update_progress(db, run_id, progress_pct=10, stage="sync_current")
            counts = sync_current_workflows(db, client, max_pages=max_pages, log=log)
            result["checked"] += counts.get("checked", 0)
            result["updated"] += counts.get("updated", 0)

        elif action == "fetch_comments":
            update_progress(db, run_id, progress_pct=20, stage="fetch_comments")
            targets = set(workflow_numbers) if workflow_numbers else None
            counts = scan_final_mail(
                db, client, workflow_numbers=targets, max_pages=max_pages, log=log
            )
            result["checked"] += counts.get("checked", 0)
            result["updated"] += counts.get("updated", 0)
            result["failed"] += counts.get("failed", 0)

        elif action == "sync_sheets":
            update_progress(db, run_id, progress_pct=30, stage="sync_sheets")
            counts = sync_to_sheets(db, full=full_sheet_sync, log=log)
            result["checked"] += counts.get("checked", 0)
            result["sheet_synced"] += counts.get("synced", 0)
            result["failed"] += counts.get("failed", 0)

        elif action == "pipeline":
            # 1) sync current + tracked open
            update_progress(db, run_id, progress_pct=5, stage="sync_workflows")
            log("INFO", "pipeline", "Stage 1/3: sync workflows")
            counts = sync_current_workflows(db, client, max_pages=max_pages, log=log)
            result["checked"] += counts.get("checked", 0)
            result["updated"] += counts.get("updated", 0)
            if workflow_numbers:
                t_counts = sync_tracked_workflows(
                    db, client, workflow_numbers=workflow_numbers, max_pages=max_pages, log=log
                )
                result["checked"] += t_counts.get("checked", 0)
                result["updated"] += t_counts.get("updated", 0)
            update_progress(
                db,
                run_id,
                progress_pct=40,
                stage="fetch_comments",
                checked_count=result["checked"],
                updated_count=result["updated"],
            )
            # 2) final mail
            log("INFO", "pipeline", "Stage 2/3: Final Mail comments")
            m_counts = scan_final_mail(db, client, max_pages=max_pages, log=log)
            result["checked"] += m_counts.get("checked", 0)
            result["updated"] += m_counts.get("updated", 0)
            result["failed"] += m_counts.get("failed", 0)
            update_progress(
                db,
                run_id,
                progress_pct=70,
                stage="sync_sheets",
                checked_count=result["checked"],
                updated_count=result["updated"],
                failed_count=result["failed"],
            )
            # 3) sheets
            log("INFO", "pipeline", "Stage 3/3: Google Sheets sync")
            try:
                s_counts = sync_to_sheets(db, full=full_sheet_sync, log=log)
                result["sheet_synced"] += s_counts.get("synced", 0)
                result["failed"] += s_counts.get("failed", 0)
            except GoogleSheetsError as exc:
                log("ERROR", "sheets", str(exc))
                result["failed"] += 1
        else:
            raise ValueError(f"Unknown action: {action}")

        update_progress(
            db,
            run_id,
            progress_pct=95,
            stage="finishing",
            checked_count=result["checked"],
            updated_count=result["updated"],
            failed_count=result["failed"],
            sheet_synced_count=result["sheet_synced"],
        )
        return result
    finally:
        if owns_client and client is not None:
            client.close()


def start_manual_run(
    *,
    action: str,
    workflow_numbers: list[str] | None = None,
    full_sheet_sync: bool = False,
    max_pages: int | None = None,
    triggered_by: str = "manual",
    scheduled_job_id: int | None = None,
    parent_run_id: int | None = None,
) -> int:
    """Create run and execute in background. Returns run_id."""
    db = SessionLocal()
    try:
        lock_key = f"action:{action}" if action != "pipeline" else "action:pipeline"
        # Global pipeline lock for concurrent safety
        if not acquire_lock(db, lock_key, owner=f"{triggered_by}:{action}"):
            raise JobConflictError(f"Job already running for {action}")
        run = create_run(
            db,
            action,
            triggered_by=triggered_by,
            scheduled_job_id=scheduled_job_id,
            parent_run_id=parent_run_id,
        )
        run_id = run.id
    finally:
        db.close()

    def _worker() -> None:
        worker_db = SessionLocal()
        try:
            try:
                result = execute_action(
                    worker_db,
                    action,
                    run_id=run_id,
                    workflow_numbers=workflow_numbers,
                    full_sheet_sync=full_sheet_sync,
                    max_pages=max_pages,
                )
                status = "success"
                if result.get("failed", 0):
                    # Partial failures still mark success unless hard exception
                    status = "success"
                finish_run(worker_db, run_id, status=status)
                if scheduled_job_id:
                    job = worker_db.query(ScheduledJob).filter(ScheduledJob.id == scheduled_job_id).first()
                    if job:
                        job.last_run_at = utc_now()
                        job.last_run_status = status
                        worker_db.add(job)
                        worker_db.commit()
            except (AuthError, AconexApiError, GoogleSheetsError, Exception) as exc:
                try:
                    worker_db.rollback()
                except Exception:
                    pass
                try:
                    finish_run(worker_db, run_id, status="failed", error_message=str(exc)[:2000])
                except Exception:
                    pass
                if scheduled_job_id:
                    try:
                        job = worker_db.query(ScheduledJob).filter(ScheduledJob.id == scheduled_job_id).first()
                        if job:
                            job.last_run_at = utc_now()
                            job.last_run_status = "failed"
                            worker_db.add(job)
                            worker_db.commit()
                    except Exception:
                        try:
                            worker_db.rollback()
                        except Exception:
                            pass
            finally:
                try:
                    worker_db.rollback()
                except Exception:
                    pass
                try:
                    release_lock(worker_db, lock_key)
                except Exception:
                    try:
                        worker_db.rollback()
                        release_lock(worker_db, lock_key)
                    except Exception:
                        pass
        finally:
            worker_db.close()

    run_in_background(_worker)
    return run_id


def run_scheduled_job(job_id: int) -> int | None:
    db = SessionLocal()
    try:
        job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
        if not job or not job.enabled:
            return None
        params: dict[str, Any] = {}
        try:
            params = json.loads(job.job_params_json or "{}")
        except json.JSONDecodeError:
            params = {}
        action = job.job_type or "pipeline"
    finally:
        db.close()

    try:
        return start_manual_run(
            action=action,
            workflow_numbers=params.get("workflow_numbers"),
            full_sheet_sync=bool(params.get("full_sheet_sync", False)),
            max_pages=params.get("max_pages"),
            triggered_by="schedule",
            scheduled_job_id=job_id,
        )
    except JobConflictError:
        return None
