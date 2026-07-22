"""XML parsing helpers for ACONEX Workflow and Mail responses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lxml import etree


def parse_xml_bytes(content: bytes) -> etree._Element | None:
    try:
        parser = etree.XMLParser(recover=True, huge_tree=True, remove_blank_text=True)
        return etree.fromstring(content, parser=parser)
    except Exception:
        return None


def local_name(element: etree._Element) -> str:
    if not isinstance(element.tag, str):
        return str(element.tag)
    return etree.QName(element.tag).localname


def children(element: etree._Element, name: str) -> list[etree._Element]:
    return [child for child in element if local_name(child) == name]


def first_child(element: etree._Element, name: str) -> etree._Element | None:
    items = children(element, name)
    return items[0] if items else None


def text_of(element: etree._Element, name: str) -> str:
    child = first_child(element, name)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def first_text(element: etree._Element, name: str) -> str:
    for item in element.iter():
        if local_name(item) == name and item.text:
            return item.text.strip()
    return ""


def descendants(element: etree._Element, name: str) -> list[etree._Element]:
    return [item for item in element.iter() if local_name(item) == name]


def attr(element: etree._Element, *names: str) -> str:
    for name in names:
        value = element.attrib.get(name)
        if value:
            return value
    # case-insensitive fallback
    lower_map = {k.lower(): v for k, v in element.attrib.items()}
    for name in names:
        value = lower_map.get(name.lower())
        if value:
            return value
    return ""


def int_attr(element: etree._Element, name: str) -> int | None:
    value = element.attrib.get(name, "")
    return int(value) if value.isdigit() else None


def workflow_number_int(workflow_number: str) -> int | None:
    match = re.search(r"(\d+)", workflow_number or "")
    return int(match.group(1)) if match else None


def step_index_from_name(step_name: str) -> int | None:
    match = re.search(r"\bstep\s*0*(\d+)\b", step_name or "", flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d+)\b", step_name or "")
    return int(match.group(1)) if match else None


@dataclass
class ParsedStep:
    workflow_id: str
    workflow_number: str
    workflow_number_int: int | None
    workflow_title: str
    workflow_status: str
    step_name: str
    step_index: int | None
    step_status: str
    step_outcome: str
    participant: str = ""
    date_completed: str = ""
    date_due: str = ""
    date_in: str = ""


@dataclass
class ParsedWorkflowPage:
    page_number: int
    total_pages: int | None
    steps: list[ParsedStep] = field(default_factory=list)


def parse_workflow_xml(content: bytes, *, page_number: int = 1) -> ParsedWorkflowPage:
    root = parse_xml_bytes(content)
    if root is None:
        return ParsedWorkflowPage(page_number=page_number, total_pages=None, steps=[])
    steps: list[ParsedStep] = []
    for wf in descendants(root, "Workflow"):
        number = text_of(wf, "WorkflowNumber")
        n_int = workflow_number_int(number)
        if n_int is None and not number:
            continue
        step_name = text_of(wf, "StepName")
        steps.append(
            ParsedStep(
                workflow_id=attr(wf, "WorkflowId", "workflowId") or number,
                workflow_number=number,
                workflow_number_int=n_int,
                workflow_title=text_of(wf, "WorkflowName") or text_of(wf, "WorkflowTitle"),
                workflow_status=text_of(wf, "WorkflowStatus"),
                step_name=step_name,
                step_index=step_index_from_name(step_name),
                step_status=text_of(wf, "StepStatus"),
                step_outcome=text_of(wf, "StepOutcome"),
                participant=text_of(wf, "Participant") or text_of(wf, "AssignedTo") or text_of(wf, "Reviewer"),
                date_completed=text_of(wf, "DateCompleted"),
                date_due=text_of(wf, "DateDue"),
                date_in=text_of(wf, "DateIn"),
            )
        )
    return ParsedWorkflowPage(
        page_number=page_number,
        total_pages=int_attr(root, "TotalPages"),
        steps=steps,
    )


@dataclass
class ParsedMail:
    mail_id: str
    mail_number: str = ""
    subject: str = ""
    sent_date: str = ""
    from_user: str = ""
    body_text: str = ""
    reference_number: str = ""


def parse_mail_list_xml(content: bytes) -> tuple[list[ParsedMail], int | None]:
    root = parse_xml_bytes(content)
    if root is None:
        return [], None
    mails: list[ParsedMail] = []
    for mail in descendants(root, "Mail"):
        mail_id = attr(mail, "MailId", "mailId")
        if not mail_id:
            continue
        from_user = ""
        from_el = first_child(mail, "FromUserDetails")
        if from_el is None:
            from_el = first_child(mail, "fromUserDetails")
        if from_el is not None:
            from_user = (
                text_of(from_el, "FullName")
                or text_of(from_el, "UserName")
                or (from_el.text or "").strip()
            )
        else:
            from_user = text_of(mail, "From") or text_of(mail, "fromUserDetails")
        mails.append(
            ParsedMail(
                mail_id=mail_id,
                mail_number=text_of(mail, "MailNo") or text_of(mail, "docno") or attr(mail, "MailNo"),
                subject=text_of(mail, "Subject") or text_of(mail, "subject"),
                sent_date=text_of(mail, "SentDate") or text_of(mail, "sentdate"),
                from_user=from_user,
                reference_number=text_of(mail, "InRefToMailNo") or text_of(mail, "inreftomailno"),
            )
        )
    return mails, int_attr(root, "TotalPages")


def extract_mail_body_text(content: bytes) -> str:
    root = parse_xml_bytes(content)
    if root is None:
        return ""
    for name in ("MailBody", "Body", "Message", "Comments", "Comment", "MailData", "Remarks", "Response"):
        value = first_text(root, name)
        if value:
            return value
    return ""


def compute_overdue(date_due: str, step_status: str, date_completed: str) -> str:
    """Simple overdue label; production can refine with real clock."""
    status = (step_status or "").strip().lower()
    if date_completed:
        return ""
    if status in {"completed", "closed", "terminate", "terminated"}:
        return ""
    if not date_due:
        return "pending" if "pending" in status or not status else ""
    # Keep raw due date indicator; detailed duration left to sheets formula / UI
    if "pending" in status or status in {"", "open", "in progress"}:
        return "pending"
    return ""


def group_steps_by_workflow(steps: list[ParsedStep]) -> dict[str, list[ParsedStep]]:
    grouped: dict[str, list[ParsedStep]] = {}
    for step in steps:
        grouped.setdefault(step.workflow_number, []).append(step)
    return grouped


def pick_best_steps(steps: list[ParsedStep]) -> list[ParsedStep]:
    """Deduplicate steps by index/name, preferring richer records."""
    by_key: dict[str, ParsedStep] = {}
    for step in steps:
        key = f"{step.step_index or 'x'}:{step.step_name or ''}"
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = step
            continue
        # Prefer record with outcome / completed date
        score_new = bool(step.step_outcome) + bool(step.date_completed) + bool(step.participant)
        score_old = bool(existing.step_outcome) + bool(existing.date_completed) + bool(existing.participant)
        if score_new >= score_old:
            by_key[key] = step
    return sorted(
        by_key.values(),
        key=lambda s: (s.step_index is None, s.step_index or 0, s.step_name),
    )


def is_completed_status(status: str) -> bool:
    s = (status or "").strip().lower()
    return any(marker in s for marker in ("completed", "closed", "terminate", "terminated"))


def review_code(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized[:1] in {"A", "B", "C"}:
        return normalized[0]
    return "P"
