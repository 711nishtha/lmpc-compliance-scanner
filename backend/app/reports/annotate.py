"""Draws bounding boxes for extracted declaration fields onto the scan image, color-coded by
the status of the rule check each field's evidence supports.

This existed only as unused (x, y, width, height) data on each ExtractedField/Evidence object
until now -- nothing in the codebase ever drew it onto an image, in the live UI or in the PDF/
DOCX reports, despite it being called out as a marquee demo feature. Found via a real Playwright
browser walkthrough of the frontend, not backend code review alone -- see
docs/ARCHITECTURE.md §4 note on this.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.rules.schema import ComplianceReport, Status

# MIRRORS frontend/src/tokens.css --color-status-* . These are the same colors the
# on-screen legend uses; if they drift, the annotated image contradicts the UI.
# OpenCV wants B,G,R (not R,G,B) -- the hex on the right is the canonical token value.
STATUS_BGR = {
    Status.PASS: (0x3B, 0x5A, 0x2E),            # #2E5A3B  vintage forest green
    Status.FAIL: (0x2B, 0x3A, 0xA6),            # #A63A2B  vintage terracotta
    Status.NEEDS_VERIFICATION: (0x14, 0x61, 0x8A),  # #8A6114  vintage ochre
    Status.NOT_APPLICABLE: (0x5A, 0x60, 0x6B),  # #6B605A  warm gray
}

# Worst-first: a box shared by multiple rules (e.g. manufacturer name/address citing the same OCR
# region, or R6-4 and the new R8-2 both citing the net-quantity region) must be drawn using the
# most serious status among them -- a FAIL must never be silently hidden behind a PASS just
# because that rule happened to run first.
STATUS_SEVERITY = {Status.FAIL: 0, Status.NEEDS_VERIFICATION: 1, Status.PASS: 2, Status.NOT_APPLICABLE: 3}

# Statuses that get no box drawn at all.
#
# NEEDS_VERIFICATION means the engine explicitly could NOT reach a finding -- no calibration
# reference, two extraction engines disagreeing, a declaration read at low confidence. Drawing a
# rectangle around a region for such a rule asserts a precision that does not exist: the box is
# whatever OCR line the evidence came from (for R7-1 that is the merged text line, not the bare
# numeral it claims to measure), so it points at an approximate region on behalf of a rule that
# reached no conclusion about it. On a real photo that reads as a confident machine finding, and
# it crowds out the boxes for rules that DID conclude something. A rule the system could not
# decide belongs in the itemised table, where its reason is stated, not drawn on the evidence
# image. NOT_APPLICABLE is excluded for the same reason -- there is nothing to point at.
#
# The severity ordering above still matters: a box shared between a FAIL and a
# NEEDS_VERIFICATION rule is still drawn, as a FAIL, because the FAIL is a real finding about
# that region. Only boxes cited exclusively by undrawn statuses disappear.
UNDRAWN_STATUSES = frozenset({Status.NEEDS_VERIFICATION, Status.NOT_APPLICABLE})


def draw_annotations(image: np.ndarray, report: ComplianceReport) -> np.ndarray:
    annotated = image.copy()
    h_img, w_img = annotated.shape[:2]

    boxes: dict[tuple[int, int, int, int], list] = {}
    for r in report.results:
        if r.status in UNDRAWN_STATUSES:
            continue
        box = r.evidence.bounding_box
        if box is None:
            continue
        key = (box.x, box.y, box.width, box.height)
        boxes.setdefault(key, []).append(r)

    for (bx, by, bw, bh), results in boxes.items():
        results.sort(key=lambda r: STATUS_SEVERITY.get(r.status, 9))
        worst = results[0]
        same_status_ids = [r.rule_id for r in results if r.status == worst.status]
        color = STATUS_BGR.get(worst.status, (140, 140, 140))
        x = max(0, min(bx, w_img - 1))
        y = max(0, min(by, h_img - 1))
        x2 = max(0, min(bx + bw, w_img))
        y2 = max(0, min(by + bh, h_img))
        cv2.rectangle(annotated, (x, y), (x2, y2), color, 2)
        label = f"{'/'.join(same_status_ids)} {worst.status.value}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_y = y if y - th - 6 >= 0 else min(h_img, y2 + th + 6)
        label_top = label_y - th - 6 if y - th - 6 >= 0 else label_y - th - baseline
        cv2.rectangle(annotated, (x, label_top), (x + tw + 6, label_top + th + 6), color, -1)
        cv2.putText(
            annotated, label, (x + 3, label_top + th + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (255, 255, 255), 1, cv2.LINE_AA,
        )
    return annotated
