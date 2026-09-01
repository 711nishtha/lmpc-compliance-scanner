"""Regression guard for a real bug found by scanning an actual product photo, not a demo mockup.

preprocess()'s deskew stage rotated an already-upright photo of a DFM/Kurkure packet by -29.9
degrees. _estimate_skew_angle took the plain median of every Hough line angle, and on a real
photo the strong straight edges are the packet's own diagonal edges, foil creases, table edges
and nutrition-table borders -- not text baselines. OCR fell from 72 regions to 9 and the scan
reported FAIL/"not found" for manufacturer, net quantity, MRP, mfg date and consumer care, all
of which are plainly printed on that pack. Five false FAILs from one bad rotation, and a false
FAIL is the worst error direction for an enforcement tool.

The fix gates on AGREEMENT among the detected lines, not on the angle's size -- see
app/ocr/preprocess.py::_estimate_skew_angle for the measured numbers.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ocr.preprocess import MIN_SKEW_LINES, _estimate_skew_angle, deskew


def _blank(h=900, w=900):
    return np.full((h, w), 255, dtype=np.uint8)


def _parallel_lines(angle_deg: float, count: int = 20) -> np.ndarray:
    """A page of consistently-sloped lines -- what genuine skew looks like to this estimator."""
    img = _blank()
    length, cx = 400, 450
    dx = int(length * np.cos(np.radians(angle_deg)))
    dy = int(length * np.sin(np.radians(angle_deg)))
    for i in range(count):
        y = 60 + i * 40
        cv2.line(img, (cx - dx // 2, y - dy // 2), (cx + dx // 2, y + dy // 2), 0, 3)
    return img


def _scattered_lines() -> np.ndarray:
    """Many strong straight edges that disagree -- what a real product photo looks like."""
    img = _blank()
    rng = np.random.default_rng(0)
    for angle in rng.uniform(-44, 44, size=40):
        x, y = rng.integers(50, 850, size=2)
        dx = int(300 * np.cos(np.radians(angle)))
        dy = int(300 * np.sin(np.radians(angle)))
        cv2.line(img, (x - dx // 2, y - dy // 2), (x + dx // 2, y + dy // 2), 0, 3)
    return img


def test_consistent_skew_is_still_detected_and_corrected():
    """The gate must not cost the estimator its actual job: a genuine, consistent skew is still
    measured. Deliberately not capped by angle -- the estimator recovers a real 30 degree
    rotation accurately, and capping would discard that to fix a problem the angle never
    indicated."""
    for truth in (-20.0, -7.0, 3.0, 12.0):
        estimated = _estimate_skew_angle(_parallel_lines(truth))
        assert abs(estimated - truth) < 1.0, f"skew {truth} estimated as {estimated}"


def test_disagreeing_edges_produce_no_rotation():
    """The real bug: strong edges that point everywhere carry no usable skew signal, and their
    median is meaningless. Must return exactly 0.0 -- leave the image alone."""
    assert _estimate_skew_angle(_scattered_lines()) == 0.0


def test_deskew_leaves_the_image_untouched_when_edges_disagree():
    """End of the same path, through the public function: no rotation reported, and the returned
    array is the input itself rather than a warped copy."""
    img = cv2.cvtColor(_scattered_lines(), cv2.COLOR_GRAY2BGR)
    out, angle = deskew(img)
    assert angle == 0.0
    assert out is img


def test_too_few_lines_is_treated_as_no_signal():
    """An agreement fraction computed from two samples is meaningless -- two lines trivially
    agree. Below the floor the conservative action is to leave the image alone."""
    img = _blank()
    cv2.line(img, (100, 100), (500, 180), 0, 3)
    cv2.line(img, (100, 300), (500, 380), 0, 3)
    assert _estimate_skew_angle(img) == 0.0


def test_a_genuine_skew_needs_enough_lines_to_be_believed():
    """Guards the floor from being raised past what real skewed text produces: a normal page of
    consistently-sloped text lines clears MIN_SKEW_LINES comfortably."""
    assert MIN_SKEW_LINES <= 20
    assert _estimate_skew_angle(_parallel_lines(8.0, count=MIN_SKEW_LINES + 2)) != 0.0
