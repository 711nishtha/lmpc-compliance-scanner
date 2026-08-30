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
