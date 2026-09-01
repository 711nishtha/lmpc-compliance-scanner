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

# A word-level confidence floor was tried here and REVERTED: it looked well-justified from one
# real deployed scan (legit reads 60-96, noise 0-33), but re-testing against demo_data's real
# Gujarati label (10_gujarati_bilingual_liquid.png) showed it silently drops genuinely CORRECT
# Gujarati words -- "ઉત્પાદન તારીખ" (production date) lost its first word and mfg-date extraction
# broke. Indian-script OCR word confidence runs measurably noisier than Latin's even when the
# read is right (complex conjuncts/matras), so one fixed floor across all three scripts causes
# more real damage than it prevents. The dominant-script fix below (MIXED_SCRIPT_NOISE_TOLERANCE)
# already structurally prevents the hallucination this floor was meant to catch -- an eng-only
# model's output alphabet has no Gujarati/Devanagari characters in it at all, so it cannot ever
# emit one, floor or no floor. Left as a documented dead end so it isn't tried again the same way.

# A merged line's minority-script character count below which it is treated as combined-model
# noise contaminating an otherwise single-script line, not genuine mixed-script content, and is
# re-classified by its MAJORITY script instead of falling back to "mixed". This is what breaks
# the vicious cycle: a "mixed" classification currently re-runs the SAME combined model that
# produced the stray character, which is structurally incapable of fixing its own hallucination
# since nothing about the input changed. The threshold is set well below what a genuine
# mixed-script line carries -- a real Hindi phrase next to a Latin email address (the case this
# whole script-selection design exists for) has many characters on both sides, not one or two.
MIXED_SCRIPT_NOISE_TOLERANCE = 2

# Speed: real numbers, profiled against a real deployed scan (a genuine 2400x1257 phone photo,
# not a flat demo mockup) -- run_ocr() split roughly evenly between the one full-image combined-
# model pass (~4s) and _refine_regions_by_script()'s per-region loop (~6s, ~167ms/region), which
# issues ONE ADDITIONAL Tesseract subprocess call per merged region. On that photo 19 of 36
# merged regions (53%) had two or fewer alphanumeric characters -- hallucinated single glyphs,
# punctuation, gridline/icon fragments -- and NONE of NET_QTY_RE/MRP_VALUE_RE/the anchor keyword
# lists can ever match something that short (shortest real anchor keyword, "rs", is itself only
# 2 characters and in practice never appears merged-alone -- see keywords.py). Refining such a
# region's script tag is a real, measured cost for zero possible extraction benefit.
# Load-bearing distinction: this does NOT discard the region or its text, only the SECOND,
# redundant OCR call -- anchor/regex matching runs on region.text regardless of whether it was
# refined, so nothing here can cause the kind of silent content loss the (reverted)
# confidence-floor attempt caused. Short simple tokens are also exactly what the first-pass
# combined model reads reliably in either script -- refinement exists for longer, more ambiguous
# lines, which this does not touch.
MIN_REFINABLE_ALNUM_CHARS = 3


class OcrUnavailableError(RuntimeError):
    pass


def _check_tesseract_available() -> None:
    if shutil.which("tesseract") is None:
        raise OcrUnavailableError(
            "Tesseract binary not found on PATH. Install tesseract-ocr with eng+hin+guj "
            "language packs (see docs/ARCHITECTURE.md §2) to enable OCR."
        )


def run_ocr(
    image: np.ndarray, langs: tuple[str, ...] = SUPPORTED_LANGS, psm: int = 3
) -> list[OcrRegion]:
    """Runs Tesseract over the image and returns line-level regions with bounding boxes,
    confidence, and a per-region dominant-script language tag.

    `psm` (page segmentation mode) controls how the FIRST pass finds word layout -- 3 is
    Tesseract's own default ("fully automatic page segmentation, no OSD"), matching this
    function's prior unconditional behaviour exactly. Real product photos (busy, multi-panel,
    icons interspersed with text) measurably do better under psm=12 ("sparse text with OSD") --
    on three real deployed scans, psm=12 found 71-152% more high-confidence words than psm=3.
    Not swapped in as the new default: field-level testing on the same three photos showed it
    is a genuine trade, not a clean win -- psm=12's different word-grouping gained one field
    (mfg date) but lost another (consumer-care email) on the same image. See
    extract_declarations_ensemble() in extraction/fields.py, which runs both and merges per
    field rather than picking one mode blindly.

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
        image, lang=lang_string, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
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
    punctuation are script-neutral and ignored). Returns "eng"/"hin"/"guj" when one script
    overwhelmingly dominates (see MIXED_SCRIPT_NOISE_TOLERANCE below); "mixed" only when more
    than one script has substantial presence, or none at all (e.g. an all-digit line) -- "mixed"
    is the signal to fall back to the combined model rather than risk a single-language model
    mangling the other script.

    A pure "any letter from a second script -> mixed" rule (the original version of this
    function) has a real failure mode, confirmed on a live deployed scan: the FIRST-pass combined
    model can itself hallucinate a stray Gujarati/Devanagari character inside an otherwise-clean
    English line (a nutrition-table gridline or lens-blur artifact misread as one glyph). That
    single stray character then makes this function call the line "mixed", which sends it back
    to be re-OCR'd by the SAME combined model that produced the hallucination -- a vicious cycle
    that can never self-correct, since nothing about the input changes between the two combined-
    model passes. Tolerating a small minority count when ENGLISH is the majority breaks that
    cycle by giving the line an eng-only re-read that would actually fix it.

    Deliberately ASYMMETRIC: the tolerance only collapses "mixed" to "eng", never to "hin"/"guj".
    A real Gujarati demo label regressed under a symmetric version of this rule: a genuinely
    Gujarati net-quantity line ("chokkho jattho 1000 ml") legitimately keeps its unit abbreviation
    in Latin script -- extremely common on real Indian labels -- so its minority side is Latin,
    not noise. Collapsing that to "guj"-only sent it to a model that is structurally incapable of
    ever producing the Latin "ml" it needs, since a single-script model's output alphabet doesn't
    include the other script at all. Only English-majority contamination is the confirmed real
    bug; a Gujarati/Hindi-majority line with a Latin minority keeps its combined-model fallback,
    which is what correctly read this line before any of these changes and still does."""
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
    counts = {"eng": latin, "hin": deva, "guj": guj}
    present = [lang for lang, count in counts.items() if count > 0]
    if len(present) <= 1:
        return present[0] if present else "mixed"

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_lang, top_count = ranked[0]
    minority_total = sum(count for _, count in ranked[1:])
    if (
        top_lang == "eng"
        and minority_total <= MIXED_SCRIPT_NOISE_TOLERANCE
        and top_count > minority_total
    ):
        return top_lang
    return "mixed"


def _refine_regions_by_script(
    image: np.ndarray, regions: list[OcrRegion], langs: tuple[str, ...]
) -> list[OcrRegion]:
    lang_string = "+".join(langs)
    refined: list[OcrRegion] = []
    for region in regions:
        if sum(c.isalnum() for c in region.text) < MIN_REFINABLE_ALNUM_CHARS:
            # Too short to ever match an anchor keyword or a NET_QTY_RE/MRP_VALUE_RE pattern --
            # see MIN_REFINABLE_ALNUM_CHARS. Keep the first-pass combined-model reading as-is
            # rather than spending a second Tesseract call on it.
            refined.append(region)
            continue
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
