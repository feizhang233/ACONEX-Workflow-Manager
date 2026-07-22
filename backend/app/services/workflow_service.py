"""Workflow tracking, sync, history and comments."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.entities import (
    TrackedWorkflow,
    Workflow,
    WorkflowComment,
    WorkflowHistory,
    WorkflowStep,
    utc_now,
)
from app.services.aconex.client import AconexClient
from app.services.aconex.xml_utils import (
    ParsedStep,
    compute_overdue,
    group_steps_by_workflow,
    is_completed_status,
    parse_workflow_xml,
    pick_best_steps,
    review_code,
    workflow_number_int,
)


LogFn = Callable[[str, str, str], None]


def _noop_log(level: str, stage: str, message: str) -> None:
    pass


def parse_workflow_number_input(text: str, *, prefix: str = "WF-") -> list[str]:
    """Parse free-form input into workflow numbers.

    Supports: 800, WF-800, 800-850 ranges, comma/newline separated lists.
    """
    text = text.strip()
    if not text:
        return []
    results: list[str] = []
    seen: set[str] = set()
    # Split on commas, newlines, semicolons, spaces (but keep ranges intact)
    tokens = re.split(r"[\s,;]+", text)
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        range_match = re.fullmatch(
            r"(?:WF[\s\-_]*)?(\d+)\s*[-–—to]+\s*(?:WF[\s\-_]*)?(\d+)",
            token,
            flags=re.IGNORECASE,
        )
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start > end:
                start, end = end, start
            if end - start > 5000:
                raise ValueError("Range too large (max 5000 numbers).")
            for n in range(start, end + 1):
                number = f"{prefix}{n}" if prefix else str(n)
                number = _normalize_number(number, prefix=prefix)
                if number not in seen:
                    seen.add(number)
                    results.append(number)
            continue
        number = _normalize_number(token, prefix=prefix)
        if number and number not in seen:
            seen.add(number)
            results.append(number)
    return results


def _normalize_number(value: str, *, prefix: str = "WF-") -> str:
    value = value.strip().upper().replace(" ", "")
    match = re.search(r"(\d+)", value)
    if not match:
        return value
    n = match.group(1)
    if value.startswith("WF"):
        return f"WF-{int(n)}"
    if prefix:
        return f"{prefix.rstrip('-')}-{int(n)}"
    return str(int(n))


def add_tracked_numbers(
    db: Session,
    numbers: list[str],
    *,
    enabled: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    created = 0
    skipped = 0
    items: list[TrackedWorkflow] = []
    for number in numbers:
        existing = db.query(TrackedWorkflow).filter(TrackedWorkflow.workflow_number == number).first()
        if existing:
            skipped += 1
            items.append(existing)
            continue
        row = TrackedWorkflow(
            workflow_number=number,
            workflow_number_int=workflow_number_int(number),
            enabled=enabled,
            notes=notes,
        )
        db.add(row)
        items.append(row)
        created += 1
    db.commit()
    for item in items:
        db.refresh(item)
    return {"created": created, "skipped": skipped, "items": items}


def list_tracked(db: Session, *, enabled_only: bool = False) -> list[TrackedWorkflow]:
    q = db.query(TrackedWorkflow).order_by(TrackedWorkflow.workflow_number_int, TrackedWorkflow.workflow_number)
    if enabled_only:
        q = q.filter(TrackedWorkflow.enabled.is_(True))
    return q.all()


def set_tracked_enabled(db: Session, tracked_id: int, enabled: bool) -> TrackedWorkflow | None:
    row = db.query(TrackedWorkflow).filter(TrackedWorkflow.id == tracked_id).first()
    if not row:
        return None
    row.enabled = enabled
    row.updated_at = utc_now()
    db.commit()
    db.refresh(row)
    return row


def delete_tracked(db: Session, tracked_id: int) -> bool:
    row = db.query(TrackedWorkflow).filter(TrackedWorkflow.id == tracked_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def _step_content_hash(step: ParsedStep, overdue: str = "", comment: str = "") -> str:
    payload = {
        "workflow_id": step.workflow_id,
        "workflow_number": step.workflow_number,
        "step_index": step.step_index,
        "step_name": step.step_name,
        "step_status": step.step_status,
        "step_outcome": step.step_outcome,
        "participant": step.participant,
        "date_due": step.date_due,
        "date_completed": step.date_completed,
        "overdue": overdue,
        "final_mail_comment": comment,
        "workflow_status": step.workflow_status,
        "workflow_title": step.workflow_title,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upsert_workflow_steps(
    db: Session,
    steps: list[ParsedStep],
    *,
    source: str = "",
) -> dict[str, int]:
    """Persist workflows + steps; return counts."""
    checked = 0
    updated = 0
    grouped = group_steps_by_workflow(steps)
    for workflow_number, raw_steps in grouped.items():
        best = pick_best_steps(raw_steps)
        if not best:
            continue
        checked += 1
        primary = best[0]
        workflow_id = primary.workflow_id or workflow_number
        wf = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
        if wf is None:
            # Also try by number
            wf = db.query(Workflow).filter(Workflow.workflow_number == workflow_number).first()
        status = primary.workflow_status
        completed = is_completed_status(status)
        # Prefer any non-empty outcome from steps
        outcome = next((s.step_outcome for s in reversed(best) if s.step_outcome), "")
        title = primary.workflow_title
        now = utc_now()
        is_new_workflow = wf is None
        if wf is None:
            wf = Workflow(
                workflow_id=workflow_id,
                workflow_number=workflow_number,
                workflow_number_int=primary.workflow_number_int,
                workflow_title=title,
                review_status=status,
                review_outcome=outcome,
                is_completed=completed,
                is_current=not completed,
                last_checked_at=now,
                last_changed_at=now,
                source=source,
            )
            db.add(wf)
            db.flush()
            updated += 1
        else:
            old_snapshot = {
                "review_status": wf.review_status,
                "review_outcome": wf.review_outcome,
                "workflow_title": wf.workflow_title,
                "is_completed": wf.is_completed,
            }
            changed = (
                wf.review_status != status
                or wf.review_outcome != outcome
                or (title and wf.workflow_title != title)
                or wf.is_completed != completed
            )
            wf.workflow_id = workflow_id
            wf.workflow_number = workflow_number
            wf.workflow_number_int = primary.workflow_number_int
            if title:
                wf.workflow_title = title
            wf.review_status = status
            wf.review_outcome = outcome
            wf.is_completed = completed
            wf.is_current = not completed
            wf.last_checked_at = now
            wf.source = source or wf.source
            if changed:
                wf.last_changed_at = now
                updated += 1
                db.add(
                    WorkflowHistory(
                        workflow_pk=wf.id,
                        workflow_id=workflow_id,
                        workflow_number=workflow_number,
                        change_type="status",
                        change_summary="Workflow status changed",
                        old_data_json=json.dumps(old_snapshot, ensure_ascii=False),
                        new_data_json=json.dumps(
                            {
                                "review_status": status,
                                "review_outcome": outcome,
                                "workflow_title": title or wf.workflow_title,
                                "is_completed": completed,
                            },
                            ensure_ascii=False,
                        ),
                        checked_at=now,
                    )
                )
            db.add(wf)
            db.flush()

        if is_new_workflow:
            db.add(
                WorkflowHistory(
                    workflow_pk=wf.id,
                    workflow_id=workflow_id,
                    workflow_number=workflow_number,
                    change_type="new",
                    change_summary="Workflow discovered",
                    new_data_json=json.dumps(
                        {
                            "workflow_number": workflow_number,
                            "review_status": status,
                            "title": title,
                        },
                        ensure_ascii=False,
                    ),
                    checked_at=now,
                )
            )
            db.flush()

        for step in best:
            overdue = compute_overdue(step.date_due, step.step_status, step.date_completed)
            # Preserve existing final mail comment when re-syncing
            existing_step = (
                db.query(WorkflowStep)
                .filter(
                    WorkflowStep.workflow_pk == wf.id,
                    WorkflowStep.step_name == step.step_name,
                    WorkflowStep.step_index == step.step_index,
                )
                .first()
            )
            comment = existing_step.final_mail_comment if existing_step else ""
            content_hash = _step_content_hash(step, overdue=overdue, comment=comment)
            if existing_step is None:
                # Fallback match by index only
                if step.step_index is not None:
                    existing_step = (
                        db.query(WorkflowStep)
                        .filter(
                            WorkflowStep.workflow_pk == wf.id,
                            WorkflowStep.step_index == step.step_index,
                        )
                        .first()
                    )
            if existing_step is None:
                row = WorkflowStep(
                    workflow_pk=wf.id,
                    workflow_id=workflow_id,
                    workflow_number=workflow_number,
                    step_index=step.step_index,
                    step_name=step.step_name or f"Step {step.step_index or ''}".strip(),
                    step_status=step.step_status,
                    step_outcome=step.step_outcome,
                    participant=step.participant,
                    date_due=step.date_due,
                    date_completed=step.date_completed,
                    date_in=step.date_in,
                    overdue=overdue,
                    content_hash=content_hash,
                    sheet_sync_status="pending",
                )
                db.add(row)
                db.flush()
                updated += 1
                db.add(
                    WorkflowHistory(
                        workflow_pk=wf.id,
                        workflow_id=workflow_id,
                        workflow_number=workflow_number,
                        step_index=step.step_index,
                        step_name=row.step_name,
                        change_type="new",
                        change_summary=f"Step added: {row.step_name or step.step_index}",
                        new_data_json=json.dumps(
                            {
                                "step_status": step.step_status,
                                "step_outcome": step.step_outcome,
                            },
                            ensure_ascii=False,
                        ),
                        checked_at=now,
                    )
                )
                db.flush()
            else:
                old = {
                    "step_status": existing_step.step_status,
                    "step_outcome": existing_step.step_outcome,
                    "participant": existing_step.participant,
                    "date_due": existing_step.date_due,
                    "date_completed": existing_step.date_completed,
                    "overdue": existing_step.overdue,
                }
                step_changed = existing_step.content_hash != content_hash
                # Detect pending -> final for history
                old_code = review_code(existing_step.step_outcome or existing_step.step_status)
                new_code = review_code(step.step_outcome or step.step_status)
                existing_step.workflow_id = workflow_id
                existing_step.workflow_number = workflow_number
                existing_step.step_index = step.step_index
                existing_step.step_name = step.step_name or existing_step.step_name
                existing_step.step_status = step.step_status
                existing_step.step_outcome = step.step_outcome
                if step.participant:
                    existing_step.participant = step.participant
                existing_step.date_due = step.date_due or existing_step.date_due
                existing_step.date_completed = step.date_completed or existing_step.date_completed
                existing_step.date_in = step.date_in or existing_step.date_in
                existing_step.overdue = overdue
                if step_changed:
                    existing_step.content_hash = content_hash
                    existing_step.sheet_sync_status = "pending"
                    existing_step.sheet_sync_error = ""
                    updated += 1
                    summary = f"Step updated: {existing_step.step_name or existing_step.step_index}"
                    if old_code == "P" and new_code in {"A", "B", "C"}:
                        summary = f"Pending→Final ({new_code}): {existing_step.step_name}"
                    db.add(
                        WorkflowHistory(
                            workflow_pk=wf.id,
                            workflow_id=workflow_id,
                            workflow_number=workflow_number,
                            step_index=existing_step.step_index,
                            step_name=existing_step.step_name,
                            change_type="status",
                            change_summary=summary,
                            old_data_json=json.dumps(old, ensure_ascii=False),
                            new_data_json=json.dumps(
                                {
                                    "step_status": step.step_status,
                                    "step_outcome": step.step_outcome,
                                    "participant": existing_step.participant,
                                    "date_due": existing_step.date_due,
                                    "date_completed": existing_step.date_completed,
                                    "overdue": overdue,
                                },
                                ensure_ascii=False,
                            ),
                            checked_at=now,
                        )
                    )
                db.add(existing_step)
    db.commit()
    return {"checked": checked, "updated": updated}


def fetch_all_pages(
    client: AconexClient,
    *,
    status: str | None = None,
    workflow_numbers: list[str] | None = None,
    max_pages: int | None = None,
    log: LogFn = _noop_log,
) -> list[ParsedStep]:
    steps: list[ParsedStep] = []
    if workflow_numbers:
        # Batch search by number (API accepts comma-separated lists)
        batch_size = 10
        pages_scanned = 0
        for i in range(0, len(workflow_numbers), batch_size):
            batch = workflow_numbers[i : i + batch_size]
            page_number = 1
            total_pages: int | None = None
            while True:
                if max_pages is not None and pages_scanned >= max_pages:
                    break
                log("INFO", "fetch", f"Search batch {batch[0]}.. page {page_number}")
                response = client.fetch_workflow_page(
                    page_number=page_number,
                    workflow_numbers=batch,
                )
                pages_scanned += 1
                page = parse_workflow_xml(response.content, page_number=page_number)
                steps.extend(page.steps)
                total_pages = total_pages or page.total_pages
                if total_pages is None or page_number >= total_pages:
                    break
                page_number += 1
            if max_pages is not None and pages_scanned >= max_pages:
                break
        return steps

    page_number = 1
    pages_scanned = 0
    total_pages: int | None = None
    while True:
        if max_pages is not None and pages_scanned >= max_pages:
            break
        log("INFO", "fetch", f"Fetch workflows status={status or 'all'} page {page_number}")
        response = client.fetch_workflow_page(page_number=page_number, status=status)
        pages_scanned += 1
        page = parse_workflow_xml(response.content, page_number=page_number)
        steps.extend(page.steps)
        total_pages = total_pages or page.total_pages
        if total_pages is None or page_number >= total_pages:
            break
        page_number += 1
    return steps


def sync_tracked_workflows(
    db: Session,
    client: AconexClient,
    *,
    workflow_numbers: list[str] | None = None,
    max_pages: int | None = None,
    log: LogFn = _noop_log,
) -> dict[str, int]:
    if workflow_numbers is None:
        tracked = list_tracked(db, enabled_only=True)
        workflow_numbers = [t.workflow_number for t in tracked]
    if not workflow_numbers:
        log("INFO", "sync", "No tracked workflows to sync.")
        return {"checked": 0, "updated": 0}
    log("INFO", "sync", f"Syncing {len(workflow_numbers)} tracked workflow(s).")
    steps = fetch_all_pages(
        client,
        workflow_numbers=workflow_numbers,
        max_pages=max_pages,
        log=log,
    )
    # Enrich by re-search for complete step set
    return upsert_workflow_steps(db, steps, source="sync_tracked")


def sync_current_workflows(
    db: Session,
    client: AconexClient,
    *,
    max_pages: int | None = None,
    also_refresh_open: bool = True,
    log: LogFn = _noop_log,
) -> dict[str, int]:
    log("INFO", "sync", "Fetching current workflows from ACONEX.")
    steps = fetch_all_pages(client, status="current", max_pages=max_pages, log=log)
    # Enrich numbers via search for full step detail
    numbers = sorted({s.workflow_number for s in steps if s.workflow_number})
    if numbers:
        log("INFO", "sync", f"Enriching {len(numbers)} current workflow(s) by number search.")
        enriched = fetch_all_pages(client, workflow_numbers=numbers, max_pages=max_pages, log=log)
        if enriched:
            steps = enriched
    counts = upsert_workflow_steps(db, steps, source="sync_current")
    if also_refresh_open:
        open_numbers = [
            w.workflow_number
            for w in db.query(Workflow)
            .filter(Workflow.is_completed.is_(False))
            .all()
            if w.workflow_number
        ]
        # Also include tracked enabled
        open_numbers.extend(t.workflow_number for t in list_tracked(db, enabled_only=True))
        open_numbers = sorted(set(open_numbers) - set(numbers))
        if open_numbers:
            log("INFO", "sync", f"Refreshing {len(open_numbers)} open workflow(s).")
            open_steps = fetch_all_pages(
                client, workflow_numbers=open_numbers, max_pages=max_pages, log=log
            )
            open_counts = upsert_workflow_steps(db, open_steps, source="sync_open")
            counts["checked"] += open_counts["checked"]
            counts["updated"] += open_counts["updated"]
    return counts


def list_workflows(
    db: Session,
    *,
    q: str | None = None,
    current_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Workflow], int]:
    query = db.query(Workflow).options(joinedload(Workflow.steps))
    if current_only:
        query = query.filter(Workflow.is_current.is_(True), Workflow.is_completed.is_(False))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Workflow.workflow_number.ilike(like)) | (Workflow.workflow_title.ilike(like))
        )
    total = query.count()
    items = (
        query.order_by(Workflow.workflow_number_int, Workflow.workflow_number)
        .offset(max(0, (page - 1) * page_size))
        .limit(page_size)
        .all()
    )
    return items, total


def get_workflow_detail(db: Session, workflow_number: str) -> Workflow | None:
    return (
        db.query(Workflow)
        .options(joinedload(Workflow.steps), joinedload(Workflow.comments))
        .filter(Workflow.workflow_number == workflow_number)
        .first()
    )


def list_history(
    db: Session,
    *,
    workflow_number: str | None = None,
    limit: int = 100,
) -> list[WorkflowHistory]:
    q = db.query(WorkflowHistory)
    if workflow_number:
        q = q.filter(WorkflowHistory.workflow_number == workflow_number)
    return q.order_by(WorkflowHistory.id.desc()).limit(limit).all()


def list_comments(
    db: Session,
    *,
    workflow_number: str | None = None,
    limit: int = 100,
) -> list[WorkflowComment]:
    q = db.query(WorkflowComment)
    if workflow_number:
        q = q.filter(WorkflowComment.workflow_number == workflow_number)
    return q.order_by(WorkflowComment.id.desc()).limit(limit).all()


def upsert_comment(db: Session, data: dict[str, Any]) -> bool:
    """Insert or update a Final Mail comment. Returns True if changed."""
    workflow_number = data["workflow_number"]
    mail_id = data["mail_id"]
    existing = (
        db.query(WorkflowComment)
        .filter(
            WorkflowComment.workflow_number == workflow_number,
            WorkflowComment.mail_id == mail_id,
        )
        .first()
    )
    wf = db.query(Workflow).filter(Workflow.workflow_number == workflow_number).first()
    fields = {
        "workflow_pk": wf.id if wf else None,
        "workflow_number": workflow_number,
        "workflow_number_int": workflow_number_int(workflow_number),
        "mail_id": mail_id,
        "mail_number": data.get("mail_number") or "",
        "mail_subject": data.get("mail_subject") or "",
        "sent_date": data.get("sent_date") or "",
        "from_user": data.get("from_user") or "",
        "comment_text": data.get("comment_text") or "",
        "doc_no": data.get("doc_no") or "",
        "review_step": data.get("review_step") or "",
        "participant": data.get("participant") or "",
        "review_outcome": data.get("review_outcome") or "",
        "review_comment": data.get("review_comment") or "",
        "source": data.get("source") or "",
    }
    if existing is None:
        db.add(WorkflowComment(**fields))
        _apply_comment_to_steps(db, workflow_number, fields)
        db.commit()
        return True
    changed = False
    for key, value in fields.items():
        if key in {"workflow_pk"}:
            continue
        if getattr(existing, key) != value and value:
            setattr(existing, key, value)
            changed = True
    if changed:
        db.add(existing)
        _apply_comment_to_steps(db, workflow_number, fields)
        db.commit()
    return changed


def _apply_comment_to_steps(db: Session, workflow_number: str, fields: dict[str, Any]) -> None:
    """Attach Final Mail text to matching steps based on review_step when possible."""
    comment = fields.get("review_comment") or fields.get("comment_text") or ""
    if not comment:
        return
    steps = db.query(WorkflowStep).filter(WorkflowStep.workflow_number == workflow_number).all()
    review_step = (fields.get("review_step") or "").lower()
    matched = False
    for step in steps:
        name = (step.step_name or "").lower()
        idx = str(step.step_index or "")
        if review_step and (review_step in name or (idx and idx in review_step)):
            step.final_mail_comment = comment
            step.sheet_sync_status = "pending"
            step.content_hash = ""  # force rehash next time
            db.add(step)
            matched = True
    if not matched and steps:
        # Prefer highest step index
        target = sorted(steps, key=lambda s: (s.step_index is None, s.step_index or 0))[-1]
        target.final_mail_comment = comment
        target.sheet_sync_status = "pending"
        db.add(target)
