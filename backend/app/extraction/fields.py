"""Regex + keyword-anchored structured field extraction from OCR output.

This is Step 4 option (a) from the build spec: fully offline, fully explainable, no external
dependency. Each extracted field retains the OCR region it came from for evidence/bounding-box
display in the report. See docs/LEGAL_REQUIREMENTS.md §4 for unit/category rules this must not
contradict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rules.schema import BoundingBox, Declarations, ExtractedField, RegionBox

from .keywords import ALL_ANCHOR_GROUPS


@dataclass
class OcrRegion:
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    language: str = "eng"


NUMBER_RE = r"[\d०-९૦-૯]+(?:[.,]\d+)?"
MRP_VALUE_RE = re.compile(rf"(?:rs\.?|₹|inr)\s*({NUMBER_RE})", re.IGNORECASE)
MRP_VALUE_BARE_RE = re.compile(rf"({NUMBER_RE})\s*(?:/-|only)?", re.IGNORECASE)
# Real bug, found from a live deployed scan: on a real Maggi photo, no genuine "NET QUANTITY:
# 70 g" text survived OCR legibly anywhere, but a completely unrelated noise region --
# "looo290l" (OCR garbage, likely a mangled fragment near a licence/batch number) -- matched
# this pattern and got reported as the net quantity, with "l" satisfying the "litre" unit
# alternative. A genuine printed quantity is essentially always preceded by whitespace, a colon,
# or the start of the region -- not welded directly onto other characters with no separation the
# way "...ooo" is welded onto "290" here. The leading negative lookbehind blocks that: `\W`
# (Python's Unicode-aware word class, which already covers letters AND digits in all three
# supported scripts -- verified directly, not assumed) requires the character immediately before
# the number to be neither a letter nor another digit, i.e. the true start of a fresh token --
# not just "not a letter", which alone still let `re.search` slide one digit later into "90l"
# and match a SUFFIX of the same noise run. A real "1L" bottle label, number directly followed
# by "L", is unaffected -- only what comes BEFORE the number is constrained.
NET_QTY_RE = re.compile(
    rf"(?<!\w)({NUMBER_RE})\s*(g|gm|gms|gram|grams|kg|kilogram|ml|milliliter|l|litre|liter|pcs|pieces|nos)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"(\d{1,2}[/-]\d{2,4}|[A-Za-z]{3,9}\s?\d{4}|\d{2}[/-]\d{2}[/-]\d{2,4})"
)
PHONE_RE = re.compile(r"(?:\+?91[-\s]?)?\d[\d\-\s]{8,13}\d")
# A tighter, POSITIVE pattern for the two well-known real Indian phone shapes: a 10-digit mobile
# starting 6-9, or a "1800" toll-free number. Real license/batch/registration numbers on Indian
# labels (confirmed against several from a live deployed scan) don't reliably avoid separators --
# one had a single stray internal space -- so "contains a separator" alone isn't a safe positive
# signal; matching a genuine phone SHAPE is. Used as the first, preferred candidate in the
# unanchored fallback scan below; PHONE_RE stays as the last-resort fallback so a real phone in
# an unrecognised format is still better than nothing.
STRICT_PHONE_RE = re.compile(
    r"(?:\+?91[-\s]?)?(?:1800[-\s]?\d{3}[-\s]?\d{3,4}|[6-9]\d{9})\b"
)
# Real bug, found from a live deployed scan: PHONE_RE is purely shape-based (any 10-15 digit
# run) with zero context awareness, so it happily matched an FSSAI/manufacturing licence number
# ("1001202500032", 13 digits) and reported it as the consumer-care phone. Real Indian packaged-
# commodity labels routinely print several long registration/licence/batch numbers near the
# consumer-care block, and any of them is shape-identical to a phone number. Skip a candidate
# region for phone/license purposes if its own text carries one of these explicit non-phone
# numeric-ID markers -- narrowly scoped to what was actually observed and to standard Indian
# label vocabulary, not a guess at every possible false-positive source.
#
# A whole-region keyword list alone was NOT enough, also confirmed on a real deployed scan: OCR
# had dropped the leading "L" from "Lic." leaving "ic No, 1001012000180", which the keyword list
# above does not catch (no "lic" substring survives). Chasing every possible OCR corruption of
# "Lic./Licence/Registration/..." is a losing game. NO_PREFIX_RE instead targets the one
# consistently reliable, general signal: a bare "No"/"No." immediately before a long digit run.
# On real Indian retail labels this is essentially always how a reference/ID number is
# introduced (Lic. No., Batch No., FSSAI No., Order No.) -- a genuine phone number is
# introduced with "Ph:"/"Call:"/"Helpline:"/"Consumer Care:" or given completely bare, never
# with "No." directly in front of it.
NON_PHONE_NUMBER_CONTEXT_RE = re.compile(
    r"\b(lic\.?|licen[cs]e|fssai|reg\.?|regd\.?|registration|batch|lot|gstin|gst)\b",
    re.IGNORECASE,
)
NO_PREFIX_RE = re.compile(r"\bno\.?\s*,?\s*$", re.IGNORECASE)


def _is_reference_number_context(text: str, match: re.Match) -> bool:
    """True if `match` (a PHONE_RE hit) looks like a licence/batch/registration number rather
    than a phone number -- either the whole region carries an explicit marker word, or the
    characters immediately before the match are a bare "No."/"No,"/"No" prefix."""
    if NON_PHONE_NUMBER_CONTEXT_RE.search(text):
        return True
    return bool(NO_PREFIX_RE.search(text[:match.start()]))
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
GUJARATI_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def _normalize_digits(s: str) -> str:
    return s.translate(DEVANAGARI_DIGITS).translate(GUJARATI_DIGITS)


# Real Tesseract misreads confirmed by re-running the actual pipeline against a real deployed
# scan (backend/tests/test_extraction.py::test_ml_ocr_misread_as_mi... captures the exact case):
# a genuine label's "500 ml" was OCR'd as region.text == "500 mi" (lowercase l -> i is one of
# the most common single-character OCR confusions, worse at the resolution real phone photos get
# downscaled to). NET_QTY_RE's unit whitelist had no tolerance for it, so a plainly legible net
# quantity declaration extracted as "not found" -- a false negative on a field a human reads
# instantly. Narrowly scoped and evidence-driven, same discipline as NET_QTY_ANCHORS' own
# docstring: add an entry here only when a REAL OCR run demonstrates the confusion, not
# speculatively. "mi" specifically is safe to always treat as "ml" in this domain -- miles are
# never a valid Legal Metrology net-quantity unit for a packaged commodity.
_UNIT_OCR_MISREADS = {
    r"\bmi\b": "ml",
}


def _normalize_unit_ocr_noise(s: str) -> str:
    for pattern, replacement in _UNIT_OCR_MISREADS.items():
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
    return s


# Real bug, found from a live deployed scan: naive substring containment ("rs" in text_lower)
# matched "teenagers" -- the MRP anchor term "rs" is a substring of "...te**ena**GE**RS**..." --
# and the region containing an unrelated nutrition-disclaimer sentence ("16+17 year old
# teenagers (ICMR, 2020)") got selected as the MRP-anchor region, with "16" extracted as if it
# were a price. A plain \bterm\b word-boundary regex does not fix this cleanly either: \b after a
# term ending in punctuation (e.g. "rs.") requires the following STRING character to be a word
# character for the boundary to fire, so "Rs. 50" (period then space) would fail to match at all.
# Instead: require the characters immediately adjacent to the match are not themselves LETTERS
# (in any of the three supported scripts), regardless of what character the anchor term itself
# starts/ends with. This blocks "rs" matching inside "teenagers" (preceded by the letter "e")
# without breaking "rs." matching "Rs. 50" (followed by a space, not a letter).
#
# Deliberately LETTER-only, not \w (which also excludes digits) -- unlike NET_QTY_RE, anchors
# like "rs"/"₹" legitimately sit directly against a digit in real printed text ("Rs50", "₹50",
# no space). Excluding digit-adjacency too would reject those real matches; only letter-adjacency
# (the actual source of the "teenagers" collision) needs to be blocked here.
_LETTER_CLASS = "A-Za-zऀ-ॿ઀-૿"


def _compile_anchor_terms() -> dict[str, list[re.Pattern]]:
    compiled: dict[str, list[re.Pattern]] = {}
    for group, lang_terms in ALL_ANCHOR_GROUPS.items():
        patterns = []
        for terms in lang_terms.values():
            for term in terms:
                patterns.append(re.compile(
                    rf"(?<![{_LETTER_CLASS}]){re.escape(term)}(?![{_LETTER_CLASS}])",
                    re.IGNORECASE,
                ))
        compiled[group] = patterns
    return compiled


_ANCHOR_PATTERNS = _compile_anchor_terms()


def _region_matches_anchor(region: OcrRegion, group: str) -> bool:
    return any(p.search(region.text) for p in _ANCHOR_PATTERNS[group])


def _find_anchor_region(regions: list[OcrRegion], group: str) -> OcrRegion | None:
    for region in regions:
        if _region_matches_anchor(region, group):
            return region
    return None


def _to_extracted_field(region: OcrRegion | None, value: str | None) -> ExtractedField:
    if region is None or value is None:
        return ExtractedField(found=False)
    return ExtractedField(
        value=value,
        raw_text_span=region.text,
        bounding_box=BoundingBox(x=region.x, y=region.y, width=region.width, height=region.height),
        ocr_confidence=region.confidence,
        language=region.language,
        found=True,
    )


def extract_declarations(regions: list[OcrRegion]) -> Declarations:
    d = Declarations()
    full_text = " \n ".join(_normalize_digits(r.text) for r in regions)

    # MRP
    mrp_region = _find_anchor_region(regions, "mrp")
    if mrp_region:
        norm = _normalize_digits(mrp_region.text)
        m = MRP_VALUE_RE.search(norm) or MRP_VALUE_BARE_RE.search(norm)
        if m:
            d.mrp_value = _to_extracted_field(mrp_region, m.group(1))
    tax_region = _find_anchor_region(regions, "tax_inclusive")
    if tax_region:
        d.mrp_inclusive_of_taxes_stated = _to_extracted_field(tax_region, "yes")

    # Net quantity
    nq_region = _find_anchor_region(regions, "net_qty")
    search_regions = [nq_region] if nq_region else regions
    for region in search_regions:
        if region is None:
            continue
        norm = _normalize_unit_ocr_noise(_normalize_digits(region.text))
        m = NET_QTY_RE.search(norm)
        if m:
            d.net_quantity_value = _to_extracted_field(region, m.group(1))
            unit = m.group(2).lower()
            d.net_quantity_unit = _to_extracted_field(region, unit)
            if unit in ("g", "gm", "gms", "gram", "grams", "kg", "kilogram"):
                d.commodity_category = d.commodity_category or "solid"
            elif unit in ("ml", "milliliter", "l", "litre", "liter"):
                d.commodity_category = d.commodity_category or "liquid"
            elif unit in ("pcs", "pieces", "nos"):
                d.commodity_category = d.commodity_category or "count"
            break

    # Mfg date
    mfg_region = _find_anchor_region(regions, "mfg_date")
    if mfg_region:
        norm = _normalize_digits(mfg_region.text)
        m = DATE_RE.search(norm)
        if m:
            d.mfg_month_year = _to_extracted_field(mfg_region, m.group(1))

    # Best before
    bb_region = _find_anchor_region(regions, "best_before")
    if bb_region:
        norm = _normalize_digits(bb_region.text)
        m = DATE_RE.search(norm)
        d.best_before_use_by = _to_extracted_field(bb_region, m.group(1) if m else bb_region.text.strip())
        d.is_perishable_category = True

    # Manufacturer
    mfr_region = _find_anchor_region(regions, "manufacturer")
    if mfr_region:
        d.manufacturer_name = _to_extracted_field(mfr_region, mfr_region.text.strip())
        # naive: next region below/adjacent often holds the address; caller may refine
        d.manufacturer_address = _to_extracted_field(mfr_region, mfr_region.text.strip())

    # Country of origin
    coo_region = _find_anchor_region(regions, "country_of_origin")
    if coo_region:
        d.country_of_origin = _to_extracted_field(coo_region, coo_region.text.strip())
        d.is_imported = True

    # Common/generic name: heuristic — largest text region that isn't matched by any anchor group
    anchor_matched_ids = {
        id(r) for group in ALL_ANCHOR_GROUPS for r in regions if _region_matches_anchor(r, group)
    }
    candidates = [r for r in regions if id(r) not in anchor_matched_ids]
    if candidates:
        best = max(candidates, key=lambda r: r.height)
        d.common_generic_name = _to_extracted_field(best, best.text.strip())

    # Consumer care
    cc_region = _find_anchor_region(regions, "consumer_care")
    if cc_region:
        block = cc_region.text
        phone_m = PHONE_RE.search(block)
        if phone_m and _is_reference_number_context(block, phone_m):
            phone_m = None
        email_m = EMAIL_RE.search(block)
        if phone_m:
            d.consumer_care_phone = _to_extracted_field(cc_region, phone_m.group(0))
        if email_m:
            d.consumer_care_email = _to_extracted_field(cc_region, email_m.group(0))
        d.consumer_care_name = _to_extracted_field(cc_region, cc_region.text.strip())
        d.consumer_care_address = _to_extracted_field(cc_region, cc_region.text.strip())
    else:
        # phone/email may appear without an explicit "consumer care" anchor. Deliberately only
        # STRICT_PHONE_RE here, no loose-shape last resort: with no "consumer care" heading to
        # anchor to, a same-region context check (no "No."/keyword left in the OCR'd text) is not
        # always enough to rule out a reference number -- confirmed on a real deployed scan, a
        # bare 13-digit licence number with zero surrounding context in its own merged region
        # slipped past every context check and got reported as a phone. A loose PHONE_RE fallback
        # here would keep confidently asserting a wrong number whenever the real phone simply
        # failed to OCR legibly, rather than correctly reporting "not found" -- and this project's
        # rule throughout is that "not found" beats a fabricated fact. The anchored branch above
        # keeps the looser PHONE_RE because being inside an actual "consumer care" block is real,
        # much stronger context that a same-region digit run really is the phone number.
        for region in regions:
            strict_m = STRICT_PHONE_RE.search(region.text)
            if strict_m and not _is_reference_number_context(region.text, strict_m):
                d.consumer_care_phone = _to_extracted_field(region, strict_m.group(0))
                break

        for region in regions:
            email_m = EMAIL_RE.search(region.text)
            if email_m and not d.consumer_care_email.found:
                d.consumer_care_email = _to_extracted_field(region, email_m.group(0))

    # Unit sale price
    usp_region = _find_anchor_region(regions, "unit_sale_price")
    if usp_region:
        norm = _normalize_digits(usp_region.text)
        m = MRP_VALUE_RE.search(norm) or MRP_VALUE_BARE_RE.search(norm)
        if m:
            d.unit_sale_price = _to_extracted_field(usp_region, m.group(1))

    # Text heights for Tier-1 font-size relative comparison
    for region in regions:
        d.text_heights_px[f"region_{id(region)}"] = region.height
    if d.mrp_value.found and d.mrp_value.bounding_box:
        d.text_heights_px["mrp_value"] = d.mrp_value.bounding_box.height
    if d.net_quantity_value.found and d.net_quantity_value.bounding_box:
        d.text_heights_px["net_quantity_value"] = d.net_quantity_value.bounding_box.height
    if d.common_generic_name.found and d.common_generic_name.bounding_box:
        d.text_heights_px["brand"] = d.common_generic_name.bounding_box.height

    # Every detected text region, for placement checks (LEGAL_REQUIREMENTS.md §10) that need to
    # reason about proximity/obstruction against *all* printed matter, not just matched fields.
    d.all_regions = [
        RegionBox(x=r.x, y=r.y, width=r.width, height=r.height, text=r.text) for r in regions
    ]

    d.image_quality_warning = _assess_image_quality(regions, d)

    _ = full_text  # retained for potential future whole-label heuristics
    return d


_QUALITY_CHECK_FIELDS = (
    # common_generic_name deliberately excluded: it falls back to "tallest unanchored region"
    # unconditionally (see the heuristic above), so it "finds" something even from pure noise --
    # not a genuine signal that any real declaration was recognized.
    "manufacturer_name", "net_quantity_value", "mfg_month_year", "mrp_value", "consumer_care_name",
)


def _assess_image_quality(regions: list[OcrRegion], d: Declarations) -> str | None:
    """Flags when the scan looks unreadable rather than genuinely non-compliant. An all-FAIL
    report can mean either "bad photo" or "bad label", and a viewer (live-demo audience or a real
    inspector) needs to tell which at a glance rather than reading every row's notes -- this was
    deferred during an earlier frontend QA pass (a blank test image produced an honest but
    ambiguous all-FAIL report) and is being closed now. Deliberately conservative: only fires when
    there's essentially nothing to work with, so a real non-compliant label with just a couple of
    legible declarations doesn't trigger a false "unreadable" warning."""
    if not regions:
        return (
            "No text was detected in this image at all. The FAIL results below likely mean the "
            "photo is unreadable (blank, blurry, wrong item, or not a product label) — not that "
            "this product fails every declaration. Retake the photo before treating this as an "
            "enforcement finding."
        )
    found_count = sum(1 for name in _QUALITY_CHECK_FIELDS if getattr(d, name).found)
    if found_count == 0 and len(regions) < 4:
        return (
            f"Only {len(regions)} short text region(s) were detected and none matched a "
            "recognizable declaration. The FAILs below likely reflect a poor-quality or "
            "off-target photo rather than a genuinely non-compliant label — verify with a "
            "clearer photo before treating this as an enforcement finding."
        )
    return None
