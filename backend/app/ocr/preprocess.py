"""Image preprocessing pipeline: deskew, contrast normalization, upscaling.

Built as a visible, inspectable pipeline per the build spec — each stage returns the intermediate
image so the API/UI can show "raw photo" vs "what we fed the OCR engine" side by side.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

MIN_TEXT_HEIGHT_PX_FOR_UPSCALE = 25


@dataclass
class PreprocessResult:
    original: np.ndarray
    deskewed: np.ndarray
    contrast_normalized: np.ndarray
    final: np.ndarray
    upscale_factor: float = 1.0
    rotation_angle_deg: float = 0.0
    stages_applied: list[str] = field(default_factory=list)


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


def upscale_if_needed(image: np.ndarray) -> tuple[np.ndarray, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    median_height = estimate_median_text_height_px(gray)
    if median_height is None or median_height >= MIN_TEXT_HEIGHT_PX_FOR_UPSCALE:
        return image, 1.0
    factor = min(3.0, MIN_TEXT_HEIGHT_PX_FOR_UPSCALE / max(median_height, 1.0))
    h, w = image.shape[:2]
    resized = cv2.resize(image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC)
    return resized, factor


def preprocess(image_bgr: np.ndarray) -> PreprocessResult:
    stages = []
    deskewed, angle = deskew(image_bgr)
    if angle:
        stages.append(f"deskew({angle:.1f} deg)")

    contrast_normalized = normalize_contrast(deskewed)
    stages.append("clahe_contrast")

    final, factor = upscale_if_needed(contrast_normalized)
    if factor > 1.0:
        stages.append(f"upscale(x{factor:.2f})")

    return PreprocessResult(
        original=image_bgr,
        deskewed=deskewed,
        contrast_normalized=contrast_normalized,
        final=final,
        upscale_factor=factor,
        rotation_angle_deg=angle,
        stages_applied=stages,
    )
