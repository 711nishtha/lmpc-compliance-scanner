"""Tesseract OCR wrapper (eng+hin+guj) with per-region script selection and confidence capture.

Requires the Tesseract binary + language data installed on the host (see ARCHITECTURE.md §2).
If unavailable, raises OcrUnavailableError with a clear message rather than crashing the API —
callers (api/scans.py) turn this into a 503 with an actionable error, and the rule engine /
extraction layer remain fully unit-testable without a live OCR install.

SPEED -- options considered and deliberately NOT taken, so they are not re-proposed as
oversights. Everything below is a real, commonly-recommended Tesseract speed-up that is wrong
for THIS pipeline specifically; what was taken instead is OCR_REFINE_WORKERS + OMP_THREAD_LIMIT
below (both measured), plus MIN_REFINABLE_ALNUM_CHARS (measured, already here).

  * `-c tessedit_do_invert=0` (skip Tesseract's light-text-on-dark retry). Measured a real ~15%
    win here with no field changes -- on demo_data, whose 12 labels are ALL dark-text-on-light,
    so the test set is structurally incapable of showing what this costs. Dark packaging with
    light text is ordinary on Indian retail shelves, and this is exactly the enforcement tool
    that must read those. Not worth 15% of one request.
  * `tessedit_char_whitelist`. Not applicable: this reads free-form bilingual label text across
    three scripts, so there is no restricted alphabet to whitelist.
  * tessdata_fast models. A host/deploy choice, not a code change -- swapping the .traineddata
    files under TESSDATA_PREFIX needs no edit here. Not adopted because its accuracy cost falls
    hardest on Devanagari/Gujarati, which is where this pipeline's reads are already most
    fragile (see MIXED_SCRIPT_NOISE_TOLERANCE, and the reverted confidence floor above).
  * tesserocr / the libtesseract C++ API, replacing pytesseract. This is the one genuinely large
    remaining win: pytesseract spawns a subprocess and reloads all three language models from
    disk on EVERY call, and this pipeline makes dozens per scan -- an in-process binding loads
    the models once. Not done here because it needs a compiled binding against the host's exact
    libtesseract, which is a real deployment risk on the free-tier container this runs on for a
    prototype. Threading the existing subprocess calls (OCR_REFINE_WORKERS) recovers a large
    part of the same win at none of that risk. If OCR latency ever needs to drop further, this
    is the next thing to do, behind a fallback to pytesseract when the binding is unavailable.
  * Cropping to a region of interest / pre-binarizing. Already handled: _crop_region crops each
    line before its refinement pass, and preprocess() caps resolution (config.py's
    MAX_PROCESSING_DIMENSION) rather than feeding Tesseract a raw 12MP photo. A pre-binarization
    pass was not added -- see the reverted grayscale experiment at OCR_REFINE_WORKERS below for
    what happens to Devanagari when this module makes Tesseract's own thresholding decisions.
"""
from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from app.extraction.fields import OcrRegion

# Tesseract multi-threads a SINGLE image via OpenMP by default. This pipeline instead gets its
# parallelism ACROSS crops (see OCR_REFINE_WORKERS), so leaving OpenMP on means each of those
# concurrent tesseract processes ALSO fans out its own thread team -- fine on a many-core dev
# box, oversubscription on the single shared vCPU this actually deploys to.
# Honest scope: measured on a 16-core dev box this is a wash for speed (within run-to-run noise
# either way, with or without the pool). It is here to bound CPU/memory contention on the small
# container, not because it was observed to make anything faster locally. Set at import, before
# the first pytesseract call, so every tesseract subprocess inherits it; setdefault rather than
# assignment so an operator who has tuned this for their host still wins.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

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

# How many refinement crops to OCR concurrently. Each _ocr_crop call is a *subprocess* spawn
# (pytesseract shells out to the tesseract binary), so the calling thread spends essentially all
# of its time blocked in wait() with the GIL released -- threads give real parallelism here, and
# a process pool would only add pickling and interpreter-startup cost on top of a subprocess we
# are already paying for.
#
# This is the single biggest speed lever in this file, because per-call FIXED cost dominates:
# every crop pays a fresh process spawn plus a full reload of the eng+hin+guj traineddata from
# disk, regardless of how tiny the crop is -- ~124ms for a crop holding one short text line.
# Measured on a 33-region composite (2486px, matching the ~36 merged regions a real deployed
# phone photo produced), full two-pass psm3+psm12 OCR: refinement was 8.5s of 11.2s -- 76% of
# the whole thing -- and this takes it to 2.3s of 4.9s. Byte-identical output: all 12 demo
# labels x both psm modes produce the same region texts AND the same extracted fields as the
# sequential version (locked in by tests/test_ocr_engine.py's two concurrency tests).
#
# Memory, measured rather than assumed -- this is the reason 4 is a fixed small number and not
# "one worker per crop". The cost of a pool here lives in CHILD processes, which never appear in
# this process's RSS, so tests/test_memory_ceiling.py structurally cannot see it. Sampling the
# tesseract children's combined RSS directly during a scan: peak 112 MB at 1 worker vs 111 MB at
# 4 -- unchanged, because peak child memory is set by the ONE full-image first pass, not by the
# refinement crops, which are single text lines and tiny by comparison. So 4 workers is close to
# free on the 512 MB Render container whose ceiling is already load-bearing (see config.py's
# MAX_PROCESSING_DIMENSION and tests/test_memory_ceiling.py -- a real OOM-kill, not a
# hypothetical), but that headroom is only free while the crops stay small; raising this to
# where several FULL-image passes could overlap would spend it. Beyond 4 the returns flatten
# anyway (6 and 8 workers measured within noise of each other), and the deploy target has far
# fewer cores than the 16-core box these numbers came from. Env-overridable so a bigger host can
# raise it without a code change.
OCR_REFINE_WORKERS = max(1, int(os.environ.get("OCR_REFINE_WORKERS", "4")))

# Speed dead end, TRIED AND REVERTED -- do not re-apply: converting the image to single-channel
# grayscale ONCE in run_ocr() and handing that to every Tesseract call. The reasoning is sound
# on paper (Tesseract greyscales and binarizes internally anyway, so the colour channels never
# reach the recognizer -- they only triple the size of the image pytesseract serialises to a
# temp file on every call) and it measured a real ~15% win with no field changes on the first
# labels tested. Testing all 12 demo labels individually, rather than a composite, showed it
# regresses real reads: on 09_hindi_manufacturer_bilingual.png the Devanagari consumer-care line
# "ग्राहक सेवा; 1800-777-8888, care@..." degraded to Latin gibberish ("Uleh Gal: ..."), losing
# consumer_care_name and consumer_care_address entirely and truncating the email; 03's "incl. of
# all taxes" also broke, dropping mrp_inclusive_of_taxes_stated. OpenCV's BT.601 luma weights
# are not what Leptonica's own conversion does, and the difference is enough to change thin
# Devanagari stroke/matra contrast against a coloured background. The colour->gray conversion is
# Tesseract's to make, not ours. Any future variant of this idea must be validated per-label
# across all 12 demo labels including the Hindi and Gujarati ones -- a composite or an
# English-only subset will not show this.


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


def _refine_one_region(
    image: np.ndarray, region: OcrRegion, langs: tuple[str, ...], lang_string: str
) -> OcrRegion:
    """Re-OCRs one merged line against its dominant script's model. Pure function of its
    arguments -- no shared mutable state -- which is what makes it safe to run these
    concurrently in _refine_regions_by_script."""
    if sum(c.isalnum() for c in region.text) < MIN_REFINABLE_ALNUM_CHARS:
        # Too short to ever match an anchor keyword or a NET_QTY_RE/MRP_VALUE_RE pattern --
        # see MIN_REFINABLE_ALNUM_CHARS. Keep the first-pass combined-model reading as-is
        # rather than spending a second Tesseract call on it.
        return region
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
        return region
    return OcrRegion(
        text=text, x=region.x, y=region.y, width=region.width, height=region.height,
        confidence=conf, language=lang,
    )


def _refine_regions_by_script(
    image: np.ndarray, regions: list[OcrRegion], langs: tuple[str, ...]
) -> list[OcrRegion]:
    """Refines every merged line concurrently (see OCR_REFINE_WORKERS for why, and for the
    measured cost this exists to cut).

    executor.map, not as_completed: it yields results in ARGUMENT order, so the returned list
    keeps exactly the region order the sequential version produced. Downstream extraction is
    order-sensitive -- extraction/fields.py walks regions in reading order to associate anchors
    with the values that follow them -- so this must not become "whichever crop finishes first."
    Each region is refined independently by _refine_one_region and nothing is shared between
    them, so concurrency changes only the timing, never the output."""
    lang_string = "+".join(langs)
    if not regions:
        return []
    if OCR_REFINE_WORKERS == 1 or len(regions) == 1:
        return [_refine_one_region(image, r, langs, lang_string) for r in regions]
    workers = min(OCR_REFINE_WORKERS, len(regions))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(
            pool.map(lambda r: _refine_one_region(image, r, langs, lang_string), regions)
        )


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
