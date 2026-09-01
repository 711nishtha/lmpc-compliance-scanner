"""Regression guard for the pre-OCR image-quality floor: real bug, not a hypothetical -- with
no floor at all, a 400x250px test photo (shorter side 250px, no OCR engine could plausibly read
individual characters at that size) went through the entire pipeline and produced a normal-
looking itemized report: 0% pass, 5 FAILs, "manufacturer not found" etc, indistinguishable from
a genuine finding. api/scans.py now calls assess_image_quality_floor() before cap_dimension/
preprocess/OCR ever touch the image, and returns a distinct IMAGE_QUALITY_INSUFFICIENT response
instead of running the rule engine when it fails. See app/config.py's MIN_IMAGE_SHORTER_SIDE_PX
/ MIN_LAPLACIAN_VARIANCE comments for how both thresholds were derived from real measurements
(all 12 demo_data labels, the known failing 400x250 case, and real deployed phone-camera scans).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import pytest

from app.ocr.preprocess import assess_image_quality_floor

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_data"
ALL_DEMO_LABELS = sorted(DEMO_DIR.glob("*.png"))


@pytest.mark.parametrize("path", ALL_DEMO_LABELS, ids=lambda p: p.name)
def test_every_demo_label_passes_the_quality_floor_at_native_size(path):
    """The floor must separate "genuinely unreadable" from "readable but the product has real
    violations" -- it must never reject a label just because it's a synthetic, pre-cropped mock
    rather than a real photo. All 12 are smaller (404-739px shorter side) than a real phone
    photo would ever be, which is exactly why 800px (a plausible-sounding guess) was rejected in
    favor of a number verified against this actual set."""
    image = cv2.imread(str(path))
    result = assess_image_quality_floor(image)
    assert result.ok, f"{path.name} incorrectly flagged: {result.reason}"


def test_downscaling_a_known_good_label_to_400x250_now_triggers_the_floor():
    """The actual real-world failing case from the field report, reproduced deterministically:
    a known-good demo label, downscaled to the exact failing resolution."""
    image = cv2.imread(str(DEMO_DIR / "01_fully_compliant.png"))
    small = cv2.resize(image, (400, 250), interpolation=cv2.INTER_AREA)
    result = assess_image_quality_floor(small)
    assert not result.ok
    assert "resolution" in result.reason.lower()
    assert result.shorter_side_px == 250


def test_a_genuinely_blurry_high_resolution_image_also_triggers_the_floor():
    """Resolution and blur are orthogonal failure modes -- a photo can have plenty of pixels and
    still be unreadable if it's badly out of focus, which a live demo could hit just as easily
    as low resolution. Confirmed empirically: naively downscaling actually *raises* the
    Laplacian-variance signal via resize aliasing, so this has to be checked on a full-resolution
    but heavily blurred image, not conflated with the resolution case above."""
    image = cv2.imread(str(DEMO_DIR / "01_fully_compliant.png"))
    blurred = cv2.GaussianBlur(image, (15, 15), 0)
    result = assess_image_quality_floor(blurred)
    assert not result.ok
    assert "blurry" in result.reason.lower()
    assert result.shorter_side_px >= 400  # resolution itself is untouched, only focus is


def test_a_sharp_full_resolution_label_is_not_flagged_as_blurry():
    image = cv2.imread(str(DEMO_DIR / "01_fully_compliant.png"))
    result = assess_image_quality_floor(image)
    assert result.ok
    assert result.laplacian_variance > 1000  # real margin above the 100 floor, not a near-miss
