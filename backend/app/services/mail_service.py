"""Final Mail comment scanning based on feedback rules."""

from __future__ import annotations

import re
from collections.abc import Callable
from html import unescape
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import FeedbackRule, Workflow, WorkflowStep
from app.services.aconex.client import AconexClient
from app.services.aconex.xml_utils import (
    extract_mail_body_text,
    parse_mail_list_xml,
    review_code,
)
from app.services.feedback_service import (
    get_enabled_rules,
    rule_matches_step,
    rule_wants_final_mail,
    step_triggered_for_mail,
)
from app.services.workflow_service import upsert_comment

WORKFLOW_NUMBER_RE = re.compile(r"\bWF[\s\-_]*0*(\d{1,9})\b", re.IGNORECASE)
FINAL_SUBJECT_RE = re.compile(r"^Final\s*\(\s*WF[-\s_]?0*(\d{3,6})\s*\)", re.IGNORECASE)

LogFn = Callable[[str, str, str], None]


def _noop_log(level: str, stage: str, message: str) -> None:
    pass


def extract_workflow_number_from_subject(subject: str) -> str | None:
    m = FINAL_SUBJECT_RE.match((subject or "").strip())
    if m:
        return f"WF-{int(m.group(1))}"
    m = WORKFLOW_NUMBER_RE.search(subject or "")
    if m:
        return f"WF-{int(m.group(1))}"
    return None


def clean_html_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def scan_final_mail(
    db: Session,
    client: AconexClient,
    *,
    workflow_numbers: set[str] | None = None,
    max_pages: int | None = None,
    log: LogFn = _noop_log,
) -> dict[str, int]:
    """Scan inbox for Final (WF-xxx) mails and store comments.

    If workflow_numbers is provided, only those are stored.
    Target set is also influenced by feedback rules (which steps trigger mail fetch).
    """
    rules = get_enabled_rules(db)
    if not any(rule_wants_final_mail(r) for r in rules):
        log("INFO", "mail", "No feedback rule requests Final Mail; skipping.")
        return {"checked": 0, "updated": 0, "failed": 0}

    target_numbers = workflow_numbers
    if target_numbers is None:
        target_numbers = _auto_target_numbers(db, rules)
        log("INFO", "mail", f"Auto target workflows for Final Mail: {len(target_numbers)}")

    if not target_numbers:
        log("INFO", "mail", "No workflows require Final Mail scan.")
        return {"checked": 0, "updated": 0, "failed": 0}

    checked = 0
    updated = 0
    failed = 0
    page_number = 1
    pages_scanned = 0
    total_pages: int | None = None
    seen_mail_ids: set[str] = set()

    while True:
        if max_pages is not None and pages_scanned >= max_pages:
            break
        log("INFO", "mail", f"Scanning mail inbox page {page_number}")
        try:
            response = client.fetch_mail_page(page_number=page_number)
        except Exception as exc:
            log("ERROR", "mail", f"Mail list failed: {exc}")
            failed += 1
            break
        pages_scanned += 1
        mails, total_pages = parse_mail_list_xml(response.content)
        for mail in mails:
            if mail.mail_id in seen_mail_ids:
                continue
            seen_mail_ids.add(mail.mail_id)
            number = extract_workflow_number_from_subject(mail.subject)
            if not number:
                # Only process Final-looking subjects to limit detail fetches
                if not (mail.subject or "").strip().lower().startswith("final"):
                    continue
                number = extract_workflow_number_from_subject(mail.subject)
            if not number or number not in target_numbers:
                continue
            checked += 1
            try:
                detail = client.fetch_mail_detail(mail.mail_id)
                body = clean_html_text(extract_mail_body_text(detail.content))
                comment_text = body or mail.subject
                changed = upsert_comment(
                    db,
                    {
                        "workflow_number": number,
                        "mail_id": mail.mail_id,
                        "mail_number": mail.mail_number,
                        "mail_subject": mail.subject,
                        "sent_date": mail.sent_date,
                        "from_user": mail.from_user,
                        "comment_text": comment_text,
                        "review_comment": comment_text,
                        "review_step": _infer_step_from_rules(db, number, rules),
                        "source": "final_mail_scan",
                    },
                )
                if changed:
                    updated += 1
                    log("INFO", "mail", f"Stored Final Mail comment for {number}")
            except Exception as exc:
                failed += 1
                log("ERROR", "mail", f"Mail detail {mail.mail_id} failed: {exc}")

        if total_pages is None or page_number >= total_pages:
            break
        page_number += 1

    return {"checked": checked, "updated": updated, "failed": failed}


def _auto_target_numbers(db: Session, rules: list[FeedbackRule]) -> set[str]:
    numbers: set[str] = set()
    steps = db.query(WorkflowStep).all()
    for step in steps:
        for rule in rules:
            if not rule_wants_final_mail(rule):
                continue
            if not rule_matches_step(rule, step):
                continue
            if step_triggered_for_mail(rule, step, db):
                numbers.add(step.workflow_number)
                break
    return numbers


def _infer_step_from_rules(db: Session, workflow_number: str, rules: list[FeedbackRule]) -> str:
    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_number == workflow_number)
        .order_by(WorkflowStep.step_index)
        .all()
    )
    for rule in rules:
        if not rule_wants_final_mail(rule):
            continue
        for step in steps:
            if rule_matches_step(rule, step) and review_code(step.step_outcome or step.step_status) in {
                "A",
                "B",
                "C",
            }:
                return step.step_name or str(step.step_index or "")
    if steps:
        return steps[-1].step_name or str(steps[-1].step_index or "")
    return ""
