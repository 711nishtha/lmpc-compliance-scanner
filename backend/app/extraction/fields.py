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
NET_QTY_RE = re.compile(
    rf"({NUMBER_RE})\s*(g|gm|gms|gram|grams|kg|kilogram|ml|milliliter|l|litre|liter|pcs|pieces|nos)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"(\d{1,2}[/-]\d{2,4}|[A-Za-z]{3,9}\s?\d{4}|\d{2}[/-]\d{2}[/-]\d{2,4})"
)
PHONE_RE = re.compile(r"(?:\+?91[-\s]?)?\d[\d\-\s]{8,13}\d")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
GUJARATI_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def _normalize_digits(s: str) -> str:
    return s.translate(DEVANAGARI_DIGITS).translate(GUJARATI_DIGITS)


def _region_matches_anchor(region: OcrRegion, group: str) -> bool:
    anchors = ALL_ANCHOR_GROUPS[group]
    text_lower = region.text.lower()
    for lang_terms in anchors.values():
        for term in lang_terms:
            if term.lower() in text_lower:
                return True
    return False


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
        norm = _normalize_digits(region.text)
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
        email_m = EMAIL_RE.search(block)
        if phone_m:
            d.consumer_care_phone = _to_extracted_field(cc_region, phone_m.group(0))
        if email_m:
            d.consumer_care_email = _to_extracted_field(cc_region, email_m.group(0))
        d.consumer_care_name = _to_extracted_field(cc_region, cc_region.text.strip())
        d.consumer_care_address = _to_extracted_field(cc_region, cc_region.text.strip())
    else:
        # phone/email may appear without an explicit "consumer care" anchor
        for region in regions:
            phone_m = PHONE_RE.search(region.text)
            if phone_m and not d.consumer_care_phone.found:
                d.consumer_care_phone = _to_extracted_field(region, phone_m.group(0))
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
