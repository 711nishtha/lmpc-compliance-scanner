"""Image preprocessing pipeline: resolution cap, deskew, contrast normalization, upscaling.

Built as a visible, inspectable pipeline per the build spec: each stage is named and recorded
in `stages_applied` so the API/report can state what was actually done to a given image.

MEMORY DISCIPLINE — read before adding a new full-resolution intermediate array here.
`PreprocessResult` used to also carry `original`, `deskewed`, and `contrast_normalized` as
separate full-resolution ndarray fields, on top of `final`. A grep of the entire codebase
(app/, tests/, frontend/src/) confirmed zero consumers of any of those three ever existed —
they were pure dead weight, kept alive for the whole request by nothing but the dataclass
itself. On a realistic simulated phone photo that measurably cost real memory (see
app/config.py's MAX_PROCESSING_DIMENSION comment for the numbers). Only `final` is a real
downstream dependency (OCR input, annotation base, stored preprocessed image, image
dimensions) and is the only full-resolution array this module now retains past its own
functions. If a "before vs after" debug view is ever built, generate a small preview
thumbnail from `final`/the stored original at display time — do not resurrect a full-res
field held for the whole request.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import (
    MAX_PROCESSING_DIMENSION,
    MAX_UPSCALED_DIMENSION,
    MIN_IMAGE_SHORTER_SIDE_PX,
    MIN_LAPLACIAN_VARIANCE,
)

MIN_TEXT_HEIGHT_PX_FOR_UPSCALE = 25


@dataclass
class ImageQualityFloorResult:
    """Outcome of assess_image_quality_floor(). `ok=False` means the caller must stop -- do not
    run OCR or the rule engine against this image at all; see api/scans.py's IMAGE_QUALITY_INSUFFICIENT
    response path. Carries the raw metrics too, not just a verdict, so the API response and any
    debug logging can show the actual numbers rather than a bare rejection."""
    ok: bool
    reason: str | None
    shorter_side_px: int
    laplacian_variance: float


def assess_image_quality_floor(image: np.ndarray) -> ImageQualityFloorResult:
    """Two independent, cheap pre-OCR gates against the two ways a photo can be genuinely
    unreadable regardless of what the label itself says: too few pixels to contain legible text
    at all, or high-resolution but badly out of focus. Deliberately run on the raw decoded image,
    before cap_dimension/preprocess touch it -- resizing measurably distorts the blur signal (a
    sharp image downscaled with area-averaging can read as MORE "sharp" by this metric due to
    aliasing, not less), so this has to see the image as actually uploaded.

    This is NOT the same thing as extraction/fields.py's _assess_image_quality: that one is a
    post-hoc heuristic over how many *fields OCR actually found*, and can only ever produce a
    soft warning attached to an otherwise-normal report. This one runs first, is purely pixel-
    level (never touches OCR output), and its failure means the rule engine never runs at all.
    See app/config.py's MIN_IMAGE_SHORTER_SIDE_PX / MIN_LAPLACIAN_VARIANCE comments for how both
    thresholds were derived from real measurements, not guessed."""
    h, w = image.shape[:2]
    shorter_side = min(h, w)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    if shorter_side < MIN_IMAGE_SHORTER_SIDE_PX:
        return ImageQualityFloorResult(
            ok=False,
            reason=(
                f"Image resolution is too low to read reliably ({w}x{h}px, shorter side "
                f"{shorter_side}px). Retake the photo closer to the label, or at a higher "
                f"resolution — the shorter side needs to be at least {MIN_IMAGE_SHORTER_SIDE_PX}px."
            ),
            shorter_side_px=shorter_side, laplacian_variance=lap_var,
        )
    if lap_var < MIN_LAPLACIAN_VARIANCE:
        return ImageQualityFloorResult(
            ok=False,
            reason=(
                "Image is too blurry to read reliably — the resolution is fine, but the photo "
                "looks out of focus. Retake it with the label held steady and in focus."
            ),
            shorter_side_px=shorter_side, laplacian_variance=lap_var,
        )
    return ImageQualityFloorResult(
        ok=True, reason=None, shorter_side_px=shorter_side, laplacian_variance=lap_var,
    )


@dataclass
class PreprocessResult:
    final: np.ndarray
    upscale_factor: float = 1.0
    rotation_angle_deg: float = 0.0
    resolution_cap_factor: float = 1.0
    stages_applied: list[str] = field(default_factory=list)


def cap_dimension(image: np.ndarray, max_dim: int = MAX_PROCESSING_DIMENSION) -> tuple[np.ndarray, float]:
    """Downscale so the longest side never exceeds `max_dim`. This is the PRIMARY memory fix:
    called first, before any other processing, so every derived array inherits the bound —
    rather than trying to chase memory down after the fact at each later stage.

    INTER_AREA is the correct choice for shrinking (unlike INTER_CUBIC/LINEAR, it area-averages
    rather than interpolates, which is both cheaper and less prone to aliasing on shrink)."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image, 1.0
    factor = max_dim / longest
    resized = cv2.resize(image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_AREA)
    return resized, factor


def _estimate_skew_angle(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = []
    for line in lines:
        x1, y1, x2, y2 = np.ravel(line)
        if x2 == x1:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -45 < angle < 45:
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))


def deskew(image: np.ndarray) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    angle = _estimate_skew_angle(gray)
    if abs(angle) < 0.5:
        return image, 0.0
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, rot_matrix, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return rotated, angle


def normalize_contrast(image: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel — handles glare/uneven lighting common on glossy packaging."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB) if image.ndim == 3 else None
    if lab is None:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(image)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_eq = clahe.apply(l_channel)
    merged = cv2.merge((l_eq, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def estimate_median_text_height_px(gray: np.ndarray) -> float | None:
    """Rough estimate via connected components on a binarized image — used only to decide
    whether an upscale pass is warranted, not as a Rule-7 measurement."""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    heights = [stats[i, cv2.CC_STAT_HEIGHT] for i in range(1, num_labels)
               if 3 < stats[i, cv2.CC_STAT_HEIGHT] < gray.shape[0] * 0.3]
    if not heights:
        return None
    return float(np.median(heights))


def upscale_if_needed(
    image: np.ndarray, max_upscaled_dimension: int = MAX_UPSCALED_DIMENSION
) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    median_height = estimate_median_text_height_px(gray)
    if median_height is None or median_height >= MIN_TEXT_HEIGHT_PX_FOR_UPSCALE:
        return image, 1.0
    factor = min(3.0, MIN_TEXT_HEIGHT_PX_FOR_UPSCALE / max(median_height, 1.0))

    h, w = image.shape[:2]
    # Absolute ceiling, independent of the relative factor above: a photo that is mostly blank
    # background (a product shot at a distance, say) can legitimately compute a tiny median text
    # height and therefore a near-3x factor -- capping the OUTPUT size here, not just the factor,
    # is what actually bounds worst-case memory regardless of how the heuristic behaves.
    longest_side = max(h, w)
    if longest_side * factor > max_upscaled_dimension:
        factor = max_upscaled_dimension / longest_side

    resized = cv2.resize(image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC)
    return resized, factor


def preprocess(image_bgr: np.ndarray) -> PreprocessResult:
    stages = []

    capped, cap_factor = cap_dimension(image_bgr)
    if cap_factor < 1.0:
        stages.append(f"resolution_cap(x{cap_factor:.3f})")

    deskewed, angle = deskew(capped)
    if angle:
        stages.append(f"deskew({angle:.1f} deg)")

    contrast_normalized = normalize_contrast(deskewed)
    stages.append("clahe_contrast")
    del deskewed  # no consumer beyond this point -- see module docstring on memory discipline

    final, factor = upscale_if_needed(contrast_normalized)
    if factor > 1.0:
        stages.append(f"upscale(x{factor:.2f})")
    del contrast_normalized

    return PreprocessResult(
        final=final,
        upscale_factor=factor,
        rotation_angle_deg=angle,
        resolution_cap_factor=cap_factor,
        stages_applied=stages,
    )
