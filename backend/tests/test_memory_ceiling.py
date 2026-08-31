"""Regression guard for a real production incident: a real phone photo (not demo_data's small,
pre-cropped label mockups) caused Render's free-tier web service to exceed its 512 MB memory
limit and get killed mid-request.

Root cause, measured (see app/config.py's MAX_PROCESSING_DIMENSION comment for the full story):
no pixel-dimension cap existed anywhere -- only upload BYTE size was capped, which does not
bound decoded array size. A realistic simulated photo (label at 3% of a 12MP frame, which is
what "photograph a whole product" actually looks like) drove preprocessing + one annotation
copy + a real Tesseract pass to 367 MB RSS -- 72% of the entire container.

This test locks in the fix with a real measurement, not a code-review assumption: it runs the
same realistic simulation through the actual pipeline and asserts peak memory stays under a
safety margin. If someone removes cap_dimension() or reintroduces a full-resolution intermediate
array, this test catches it with a number, not a guess.
"""
import gc
import os

import cv2
import numpy as np
import psutil
import pytest

from app.ocr.engine import OcrUnavailableError, run_ocr
from app.ocr.preprocess import cap_dimension, preprocess
from app.reports.annotate import draw_annotations
from app.rules.engine import run_all_checks
from app.extraction.fields import extract_declarations

DEMO_LABEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "demo_data", "01_fully_compliant.png"
)

# Comfortably under Render free tier's 512 MB container, leaving headroom for FastAPI's own
# baseline (~70-100 MB) and PDF/DOCX generation on top of this. Measured after the fix: ~192 MB
# for the moderate case, ~295 MB for a worst-case 48MP photo. 400 MB is a safety-margined gate,
# not the measured number itself -- so small, legitimate future changes don't make this flaky.
MEMORY_CEILING_MB = 400


def _rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1_048_576


def _simulate_real_photo(frame_h: int, frame_w: int, label_frac_pos: tuple[int, int]) -> np.ndarray:
    """A small, real label pasted onto a large blank frame -- simulates photographing a whole
    product (bottle/packet) rather than a pre-cropped label mockup like demo_data's raw files."""
    label = cv2.imread(DEMO_LABEL)
    assert label is not None, f"demo label not found at {DEMO_LABEL}"
    canvas = np.full((frame_h, frame_w, 3), 200, dtype=np.uint8)
    lh, lw = label.shape[:2]
    y, x = label_frac_pos
    canvas[y:y + lh, x:x + lw] = label
    return canvas


@pytest.mark.parametrize(
    "frame_h,frame_w,pos,label_desc",
    [
        (3024, 4032, (400, 600), "12MP phone photo, label ~3% of frame"),
        (6000, 8000, (800, 1200), "48MP phone photo, label <1% of frame"),
    ],
)
def test_realistic_photo_stays_under_memory_ceiling(frame_h, frame_w, pos, label_desc):
    if shutil_which_tesseract_missing():
        pytest.skip("Tesseract not installed in this environment")

    gc.collect()
    baseline = _rss_mb()

    photo = _simulate_real_photo(frame_h, frame_w, pos)
    image, cap_factor = cap_dimension(photo)
    pre = preprocess(image)
    annotated = draw_annotations(pre.final, _dummy_report())
    regions = run_ocr(pre.final)

    peak = _rss_mb()
    delta = peak - baseline

    assert delta < MEMORY_CEILING_MB, (
        f"{label_desc}: preprocessing + annotation + OCR used {delta:.0f} MB "
        f"(ceiling {MEMORY_CEILING_MB} MB) -- this is the exact failure mode that OOM-killed "
        f"the deployed Render instance. cap_dimension()/MAX_UPSCALED_DIMENSION regressed."
    )
    # The whole point of the cap: the OUTPUT is bounded regardless of input size.
    assert max(pre.final.shape[:2]) <= 3200, "upscale_if_needed's absolute ceiling was not applied"
    assert len(regions) > 0, "OCR must still find the label text after downscaling — not just cheap"


def test_cap_dimension_is_a_noop_on_already_small_images():
    """demo_data's own mockups (all under 1200px) must pass through unchanged -- the cap exists
    for real photos, not to needlessly degrade the images this project was actually tested on."""
    small = cv2.imread(DEMO_LABEL)
    capped, factor = cap_dimension(small)
    assert factor == 1.0
    assert capped.shape == small.shape


def shutil_which_tesseract_missing() -> bool:
    import shutil
    return shutil.which("tesseract") is None


def _dummy_report():
    """Minimal ComplianceReport-shaped object -- draw_annotations only reads .results for
    bounding-box evidence, and an empty list exercises the same array-copy cost this test cares
    about without depending on real rule-engine output."""
    from app.rules.schema import ComplianceReport

    return ComplianceReport(results=[])
