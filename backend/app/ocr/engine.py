"""Tesseract OCR wrapper (eng+hin+guj) with per-region script selection and confidence capture.

Requires the Tesseract binary + language data installed on the host (see ARCHITECTURE.md §2).
If unavailable, raises OcrUnavailableError with a clear message rather than crashing the API —
callers (api/scans.py) turn this into a 503 with an actionable error, and the rule engine /
extraction layer remain fully unit-testable without a live OCR install.
"""
from __future__ import annotations

import shutil

import numpy as np

from app.extraction.fields import OcrRegion

SUPPORTED_LANGS = ("eng", "hin", "guj")

DEVANAGARI_RANGE = (0x0900, 0x097F)
GUJARATI_RANGE = (0x0A80, 0x0AFF)


class OcrUnavailableError(RuntimeError):
    pass


def _check_tesseract_available() -> None:
    if shutil.which("tesseract") is None:
        raise OcrUnavailableError(
            "Tesseract binary not found on PATH. Install tesseract-ocr with eng+hin+guj "
            "language packs (see docs/ARCHITECTURE.md §2) to enable OCR."
        )


def run_ocr(image: np.ndarray, langs: tuple[str, ...] = SUPPORTED_LANGS) -> list[OcrRegion]:
    """Runs Tesseract over the image and returns line-level regions with bounding boxes,
    confidence, and a per-region dominant-script language tag.

    Two passes: (1) the combined eng+hin+guj model gives word/line layout (bounding boxes,
    merged into lines by _merge_adjacent_words) -- layout detection isn't script-dependent, so
    one pass suffices for that. (2) each merged line is re-OCR'd against only its dominant
    script's language model -- see _dominant_script / _refine_regions_by_script.

    This replaces always trusting the combined model's own character classification, but it is
    NOT confidence-based selection among candidates -- an earlier version of this function tried
    "run combined+eng+hin+guj on the crop and keep whichever comes back with the highest average
    confidence," and that measurably picked the WRONG answer: on a real Tesseract run against
    demo_data, the combined model misread "200 g" as "200 <Gujarati digit>" at confidence 90.5,
    beating the correct eng-only reading "200g" at confidence 86.0. Tesseract can be confidently
    wrong, so confidence isn't a trustworthy tiebreaker here. Character-shape script
    classification of the initial (layout-pass) reading is used instead: a region is only
    restricted to a single language model when every letter in it belongs to one script;
    anything with letters from more than one script (e.g. a Hindi anchor phrase followed by a
    Latin email address -- hin-only OCR mangles the email badly, confirmed empirically) falls
    back to the combined model, which handles genuinely mixed-script lines better than any single
    language alone. See scripts/run_real_ocr_pipeline.py for the before/after this was validated
    against."""
    _check_tesseract_available()
    import pytesseract  # imported lazily so module import doesn't require the binary

    lang_string = "+".join(langs)
    data = pytesseract.image_to_data(
        image, lang=lang_string, output_type=pytesseract.Output.DICT
    )
    regions: list[OcrRegion] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf_raw = data["conf"][i]
        try:
            conf = float(conf_raw)
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        regions.append(
            OcrRegion(
                text=text,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                confidence=conf,
                language=lang_string,
            )
        )
    merged = _merge_adjacent_words(regions)
    return _refine_regions_by_script(image, merged, langs)


def _crop_region(image: np.ndarray, region: OcrRegion, pad: int = 15) -> np.ndarray:
    # pad must be generous enough to avoid clipping descenders (g/j/p/q) and matra/vowel signs
    # that extend past a word's reported bounding box -- pad=4 measurably misread "200 g" as
    # "200q" (and, on the whole-image combined-model pass over the same crop region, as a
    # Gujarati digit) purely from a clipped descender loop; pad=15 fixed it. pad=30 overshoots
    # far enough to catch the label's border rectangle and made results worse, so this isn't
    # "more padding is always better" -- it's empirically tuned, see
    # scripts/run_real_ocr_pipeline.py for the before/after.
    h, w = image.shape[:2]
    y0, y1 = max(0, region.y - pad), min(h, region.y + region.height + pad)
    x0, x1 = max(0, region.x - pad), min(w, region.x + region.width + pad)
    return image[y0:y1, x0:x1]


def _ocr_crop(crop: np.ndarray, lang: str) -> tuple[str, float]:
    """Re-OCRs a single cropped line against one language model (--psm 7: treat as one text
    line, matching what _merge_adjacent_words already produced). Returns (text, avg confidence);
    confidence is -1.0 for an empty/failed read so it always loses the max() comparison."""
    import pytesseract

    if crop.size == 0:
        return "", -1.0
    data = pytesseract.image_to_data(
        crop, lang=lang, config="--psm 7", output_type=pytesseract.Output.DICT
    )
    words, confs = [], []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        words.append(text)
        confs.append(conf)
    if not words:
        return "", -1.0
    return " ".join(words), sum(confs) / len(confs)


def _dominant_script(text: str) -> str:
    """Classifies a region's dominant script by the Unicode block of its letters (digits and
    punctuation are script-neutral and ignored). Returns "eng"/"hin"/"guj" only when every
    letter present belongs to that one script; "mixed" if letters from more than one script are
    present (or none at all, e.g. an all-digit line) -- "mixed" is the signal to fall back to
    the combined model rather than risk a single-language model mangling the other script."""
    latin = deva = guj = 0
    for c in text:
        if not c.isalpha():
            continue
        code = ord(c)
        if DEVANAGARI_RANGE[0] <= code <= DEVANAGARI_RANGE[1]:
            deva += 1
        elif GUJARATI_RANGE[0] <= code <= GUJARATI_RANGE[1]:
            guj += 1
        elif c.isascii():
            latin += 1
    present = [lang for lang, count in (("eng", latin), ("hin", deva), ("guj", guj)) if count > 0]
    return present[0] if len(present) == 1 else "mixed"


def _refine_regions_by_script(
    image: np.ndarray, regions: list[OcrRegion], langs: tuple[str, ...]
) -> list[OcrRegion]:
    lang_string = "+".join(langs)
    refined: list[OcrRegion] = []
    for region in regions:
        crop = _crop_region(image, region)
        script = _dominant_script(region.text)
        if script in langs:
            text, conf = _ocr_crop(crop, script)
            lang = script
            if conf < 0:  # single-language model produced nothing usable -- fall back
                text, conf = _ocr_crop(crop, lang_string)
                lang = lang_string
        else:
            text, conf = _ocr_crop(crop, lang_string)
            lang = lang_string
        if conf < 0:
            # every candidate came back empty (e.g. a crop too small/blank) -- keep the
            # original combined-model line rather than discarding it.
            refined.append(region)
            continue
        refined.append(
            OcrRegion(
                text=text, x=region.x, y=region.y, width=region.width, height=region.height,
                confidence=conf, language=lang,
            )
        )
    return refined


def _merge_adjacent_words(
    regions: list[OcrRegion], y_tolerance_ratio: float = 0.4, x_gap_ratio: float = 2.5
) -> list[OcrRegion]:
    """Merges word-level boxes on the same line into line-level regions so keyword anchors
    (e.g. 'MRP Rs. 149') can match across word boundaries.

    Thresholds scale with each region's text height rather than using fixed pixel constants:
    preprocessing may upscale the image (see ocr/preprocess.py upscale_if_needed), which scales
    word gaps in pixel space right along with text height, so a fixed-pixel gap silently
    truncates lines on upscaled images (found via a real Tesseract run on demo_data, not a
    synthetic test — see scripts/run_real_ocr_pipeline.py).

    Clusters words into lines by y first, then sorts each line by x, rather than sorting all
    words by (y, x) directly. Tesseract reports a slightly different y per word even on one
    visual line (real OCR noise -- worse on Devanagari/Gujarati text, where matras/vowel signs
    shift a word's reported bounding box), so a plain (y, x) sort can put a word from later in
    the line before one earlier in it whenever their y's happen to differ by a few px. That
    silently broke merging: the walk would compare against the wrong "next" word, see a huge x
    gap, and give up on a line that should have merged -- confirmed on a real Tesseract run
    against demo_data (a Hindi consumer-care line's phone/email got permanently split off from
    its label). Clustering by y first makes the within-line x-sort immune to that noise."""
    if not regions:
        return regions
    regions_by_y = sorted(regions, key=lambda r: r.y)
    lines: list[list[OcrRegion]] = []
    for r in regions_by_y:
        for line in lines:
            ref = line[0]
            y_tolerance = max(8, max(ref.height, r.height) * y_tolerance_ratio)
            if abs(r.y - ref.y) <= y_tolerance:
                line.append(r)
                break
        else:
            lines.append([r])

    merged: list[OcrRegion] = []
    for line in lines:
        line_sorted = sorted(line, key=lambda r: r.x)
        current = line_sorted[0]
        for nxt in line_sorted[1:]:
            ref_height = max(current.height, nxt.height)
            x_gap = max(40, ref_height * x_gap_ratio)
            close_enough = (nxt.x - (current.x + current.width)) <= x_gap
            if close_enough:
                new_text = f"{current.text} {nxt.text}"
                x = min(current.x, nxt.x)
                y = min(current.y, nxt.y)
                right = max(current.x + current.width, nxt.x + nxt.width)
                bottom = max(current.y + current.height, nxt.y + nxt.height)
                current = OcrRegion(
                    text=new_text, x=x, y=y, width=right - x, height=bottom - y,
                    confidence=min(current.confidence, nxt.confidence), language=current.language,
                )
            else:
                merged.append(current)
                current = nxt
        merged.append(current)
    merged.sort(key=lambda r: (r.y, r.x))
    return merged
