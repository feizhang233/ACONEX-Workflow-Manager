"""Unit tests for XML parsing and number input."""

from app.services.aconex.xml_utils import parse_workflow_xml, review_code, pick_best_steps
from app.services.workflow_service import parse_workflow_number_input
from tests.conftest import SAMPLE_WORKFLOW_XML


def test_parse_workflow_xml():
    page = parse_workflow_xml(SAMPLE_WORKFLOW_XML)
    assert page.total_pages == 1
    assert len(page.steps) == 3
    numbers = {s.workflow_number for s in page.steps}
    assert "WF-800" in numbers
    assert "WF-801" in numbers
    step2 = next(s for s in page.steps if s.step_name == "Step 2")
    assert step2.step_index == 2
    assert step2.participant == "Bob"


def test_pick_best_steps():
    page = parse_workflow_xml(SAMPLE_WORKFLOW_XML)
    from app.services.aconex.xml_utils import group_steps_by_workflow

    grouped = group_steps_by_workflow(page.steps)
    best = pick_best_steps(grouped["WF-800"])
    assert len(best) == 2


def test_parse_number_input_range():
    numbers = parse_workflow_number_input("800-802")
    assert numbers == ["WF-800", "WF-801", "WF-802"]


def test_parse_number_input_mixed():
    numbers = parse_workflow_number_input("WF-900, 901\n802")
    assert "WF-900" in numbers
    assert "WF-901" in numbers
    assert "WF-802" in numbers


def test_review_code():
    assert review_code("A-Approved") == "A"
    assert review_code("Pending") == "P"
    assert review_code("B") == "B"
