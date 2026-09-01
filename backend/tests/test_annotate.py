"""Unit tests for annotate.draw_annotations -- specifically the worst-status-wins behavior for a
bounding box shared by multiple rules (e.g. R6-4 and R8-2 both citing the net-quantity region).
A regression test for a real bug found during frontend QA: the box was drawn using whichever
rule happened to run first, which could silently hide a FAIL behind an earlier PASS's green box.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.reports.annotate import STATUS_BGR, draw_annotations
from app.rules.schema import BoundingBox, ComplianceReport, Evidence, RuleResult, Status


def _result(rule_id, status, box):
    return RuleResult(
        rule_id=rule_id, rule_reference="Rule X", requirement_text="...", status=status,
        evidence=Evidence(bounding_box=box),
    )


def test_shared_box_uses_worst_status_not_first_rule():
    box = BoundingBox(x=10, y=10, width=50, height=20)
    # PASS is listed first, FAIL second -- the drawn box must still reflect FAIL.
    report = ComplianceReport(results=[
        _result("R6-4", Status.PASS, box),
        _result("R8-2", Status.FAIL, box),
    ])
    image = np.full((100, 100, 3), 255, dtype=np.uint8)
    annotated = draw_annotations(image, report)
    # The FAIL color must appear in the box region. Pulled from STATUS_BGR rather than hardcoded
    # so this test verifies the worst-status-wins BEHAVIOR and survives a palette change (the
    # status colors are design tokens mirrored from frontend/src/tokens.css — see
    # docs/DESIGN_SYSTEM.md §3).
    region = annotated[10:30, 10:60]
    fail_bgr = np.array(STATUS_BGR[Status.FAIL])
    pass_bgr = np.array(STATUS_BGR[Status.PASS])
    assert np.any(np.all(region == fail_bgr, axis=-1)), "FAIL color not found in shared box"
    assert not np.any(np.all(region == pass_bgr, axis=-1)), "PASS color should not win over FAIL"


def test_no_evidence_box_is_skipped_without_error():
    report = ComplianceReport(results=[
        RuleResult(rule_id="R6-9", rule_reference="Rule X", requirement_text="...", status=Status.FAIL),
    ])
    image = np.full((50, 50, 3), 255, dtype=np.uint8)
    annotated = draw_annotations(image, report)
    assert annotated.shape == image.shape


def test_needs_verification_boxes_are_not_drawn():
    """A NEEDS_VERIFICATION result is the engine saying it could not reach a finding. Drawing a
    rectangle for it asserts a precision that does not exist -- the box is whatever OCR line the
    evidence came from, not a measured region -- and it reads on the image as a confident machine
    finding. Such a rule belongs in the itemised table where its reason is stated."""
    import numpy as np

    from app.reports.annotate import draw_annotations
    from app.rules.schema import BoundingBox, ComplianceReport, Evidence, RuleResult, Status

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    report = ComplianceReport(results=[
        RuleResult(
            rule_id="R7-1", rule_reference="Rule 7(2)", requirement_text="x",
            status=Status.NEEDS_VERIFICATION,
            evidence=Evidence(bounding_box=BoundingBox(x=10, y=10, width=100, height=40)),
        )
    ])
    annotated = draw_annotations(image, report)
    assert np.array_equal(annotated, image), "no box should be drawn for NEEDS_VERIFICATION"


def test_a_box_shared_with_a_real_finding_is_still_drawn():
    """Only boxes cited exclusively by undrawn statuses disappear. A region a FAIL points at is a
    real finding and must survive a NEEDS_VERIFICATION rule citing the same region."""
    import numpy as np

    from app.reports.annotate import draw_annotations
    from app.rules.schema import BoundingBox, ComplianceReport, Evidence, RuleResult, Status

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    box = BoundingBox(x=10, y=60, width=100, height=40)
    report = ComplianceReport(results=[
        RuleResult(rule_id="R7-1", rule_reference="r", requirement_text="x",
                   status=Status.NEEDS_VERIFICATION, evidence=Evidence(bounding_box=box)),
        RuleResult(rule_id="R6-4", rule_reference="r", requirement_text="x",
                   status=Status.FAIL, evidence=Evidence(bounding_box=box)),
    ])
    annotated = draw_annotations(image, report)
    assert not np.array_equal(annotated, image)


def test_a_manually_verified_rule_gets_its_box_back():
    """Verification turns NEEDS_VERIFICATION into PASS, so the region stops being undrawn -- the
    annotated image has to be regenerated for that to show, which api/scans.py does on verify."""
    import numpy as np

    from app.reports.annotate import draw_annotations
    from app.rules.schema import BoundingBox, ComplianceReport, Evidence, RuleResult, Status

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    report = ComplianceReport(results=[
        RuleResult(
            rule_id="R7-1", rule_reference="r", requirement_text="x", status=Status.PASS,
            original_status=Status.NEEDS_VERIFICATION, verified_by="admin@example.com",
            evidence=Evidence(bounding_box=BoundingBox(x=10, y=10, width=100, height=40)),
        )
    ])
    assert not np.array_equal(draw_annotations(image, report), image)
