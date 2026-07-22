"""APScheduler integration with DB-persisted jobs."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.entities import ScheduledJob, utc_now
from app.services.pipeline import run_scheduled_job

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="Europe/Belgrade")
    return _scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
    reload_jobs_from_db()


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None


def _job_id(db_id: int) -> str:
    return f"scheduled_job_{db_id}"


def _fire(job_id: int) -> None:
    logger.info("Firing scheduled job %s", job_id)
    try:
        run_scheduled_job(job_id)
    except Exception:
        logger.exception("Scheduled job %s failed to start", job_id)


def build_trigger(job: ScheduledJob):
    tz_name = job.timezone or "Europe/Belgrade"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Belgrade")

    stype = job.schedule_type or "interval_minutes"
    if stype == "interval_minutes":
        minutes = job.interval_value or 60
        return IntervalTrigger(minutes=max(1, minutes), timezone=tz)
    if stype == "interval_hours":
        hours = job.interval_value or 1
        return IntervalTrigger(hours=max(1, hours), timezone=tz)
    if stype == "daily":
        hour, minute = _parse_hhmm(job.daily_time or "10:00")
        return CronTrigger(hour=hour, minute=minute, timezone=tz)
    if stype == "weekly":
        hour, minute = _parse_hhmm(job.daily_time or "10:00")
        weekdays = json.loads(job.weekdays_json or "[0,1,2,3,4]")
        # APScheduler: mon=0 ... sun=6 matches our convention
        day_of_week = ",".join(str(int(d)) for d in weekdays) if weekdays else "0-4"
        return CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=tz)
    if stype == "cron":
        expr = (job.cron_expression or "0 10 * * 1-5").strip()
        parts = expr.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=tz,
            )
        raise ValueError(f"Invalid cron expression: {expr}")
    raise ValueError(f"Unsupported schedule_type: {stype}")


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = (value or "10:00").strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour % 24, minute % 60


def register_job(job: ScheduledJob) -> None:
    scheduler = get_scheduler()
    jid = _job_id(job.id)
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)
    if not job.enabled:
        return
    trigger = build_trigger(job)
    scheduler.add_job(
        _fire,
        trigger=trigger,
        id=jid,
        args=[job.id],
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    # Update next_run_at
    aps_job = scheduler.get_job(jid)
    if aps_job and aps_job.next_run_time:
        db = SessionLocal()
        try:
            row = db.query(ScheduledJob).filter(ScheduledJob.id == job.id).first()
            if row:
                nrt = aps_job.next_run_time
                if nrt.tzinfo is not None:
                    nrt = nrt.replace(tzinfo=None)
                row.next_run_at = nrt
                db.add(row)
                db.commit()
        finally:
            db.close()


def unregister_job(job_id: int) -> None:
    scheduler = get_scheduler()
    jid = _job_id(job_id)
    if scheduler.get_job(jid):
        scheduler.remove_job(jid)


def reload_jobs_from_db() -> None:
    db = SessionLocal()
    try:
        jobs = db.query(ScheduledJob).all()
        for job in jobs:
            try:
                register_job(job)
            except Exception:
                logger.exception("Failed to register job %s", job.id)
    finally:
        db.close()


def create_scheduled_job(db: Session, data: dict[str, Any]) -> ScheduledJob:
    job = ScheduledJob(
        name=data["name"],
        enabled=data.get("enabled", True),
        schedule_type=data.get("schedule_type", "interval_minutes"),
        interval_value=data.get("interval_value"),
        daily_time=data.get("daily_time"),
        weekdays_json=json.dumps(data.get("weekdays") or [0, 1, 2, 3, 4]),
        cron_expression=data.get("cron_expression"),
        timezone=data.get("timezone") or "Europe/Belgrade",
        job_type=data.get("job_type") or "pipeline",
        job_params_json=json.dumps(data.get("job_params") or {}),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    register_job(job)
    return job


def update_scheduled_job(db: Session, job_id: int, data: dict[str, Any]) -> ScheduledJob | None:
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        return None
    for field in (
        "name",
        "enabled",
        "schedule_type",
        "interval_value",
        "daily_time",
        "cron_expression",
        "timezone",
        "job_type",
    ):
        if field in data and data[field] is not None:
            setattr(job, field, data[field])
    if "weekdays" in data and data["weekdays"] is not None:
        job.weekdays_json = json.dumps(data["weekdays"])
    if "job_params" in data and data["job_params"] is not None:
        job.job_params_json = json.dumps(data["job_params"])
    job.updated_at = utc_now()
    db.add(job)
    db.commit()
    db.refresh(job)
    register_job(job)
    return job


def delete_scheduled_job(db: Session, job_id: int) -> bool:
    job = db.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
    if not job:
        return False
    unregister_job(job_id)
    db.delete(job)
    db.commit()
    return True


def job_to_dict(job: ScheduledJob) -> dict[str, Any]:
    try:
        weekdays = json.loads(job.weekdays_json or "[]")
    except json.JSONDecodeError:
        weekdays = []
    try:
        params = json.loads(job.job_params_json or "{}")
    except json.JSONDecodeError:
        params = {}
    return {
        "id": job.id,
        "name": job.name,
        "enabled": job.enabled,
        "schedule_type": job.schedule_type,
        "interval_value": job.interval_value,
        "daily_time": job.daily_time,
        "weekdays": weekdays,
        "cron_expression": job.cron_expression,
        "timezone": job.timezone,
        "job_type": job.job_type,
        "job_params": params,
        "last_run_at": job.last_run_at,
        "last_run_status": job.last_run_status,
        "next_run_at": job.next_run_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
