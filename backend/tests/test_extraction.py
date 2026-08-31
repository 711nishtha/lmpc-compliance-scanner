import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.fields import OcrRegion, extract_declarations
from app.rules.engine import run_all_checks
from app.rules.schema import Status


def region(text, x=0, y=0, w=100, h=20, conf=90.0, lang="eng"):
    return OcrRegion(text=text, x=x, y=y, width=w, height=h, confidence=conf, language=lang)


def test_extracts_mrp_and_tax_inclusive():
    regions = [region("MRP Rs. 149/- incl. of all taxes")]
    d = extract_declarations(regions)
    assert d.mrp_value.found and d.mrp_value.value == "149"
    assert d.mrp_inclusive_of_taxes_stated.found


def test_extracts_net_quantity_and_infers_category():
    regions = [region("Net Wt. 250 g")]
    d = extract_declarations(regions)
    assert d.net_quantity_value.value == "250"
    assert d.net_quantity_unit.value == "g"
    assert d.commodity_category == "solid"


def test_mrp_anchor_does_not_match_substring_of_an_unrelated_word():
    """Real bug, found from a live deployed scan on an actual Maggi photo: naive substring
    matching found the MRP anchor 'rs' inside 'teenage-RS' and reported '16' (from '16+17 year
    old teenagers') as the MRP. _region_matches_anchor now requires letter-adjacency, not just
    substring containment."""
    regions = [region("16+17 year old teenagers (ICMR, 2020)")]
    d = extract_declarations(regions)
    assert not d.mrp_value.found


def test_net_quantity_does_not_match_inside_ocr_noise():
    """Real bug, found from the same deployed scan: a garbled noise region ('looo290l', likely a
    mangled fragment near a licence number) matched the net-quantity pattern via its trailing
    bare 'l' unit, reporting '290' as the net quantity when the real label said '70 g'. A genuine
    quantity is never welded directly onto other characters with no separation."""
    regions = [region("looo290l")]
    d = extract_declarations(regions)
    assert not d.net_quantity_value.found


def test_consumer_care_phone_does_not_match_a_licence_number():
    """Real bug, found from the same deployed scan: a licence number ('1001202500032', shape-
    identical to a phone number) got reported as the consumer-care phone. Covers both the
    explicit-keyword case and the case where OCR dropped the leading 'L' from 'Lic.' leaving a
    bare 'No.' prefix with no recognisable keyword left."""
    d1 = extract_declarations([region("Lic. No, 1001012000180")])
    assert not d1.consumer_care_phone.found
    d2 = extract_declarations([region("ic No, 1001012000180")])  # leading "L" dropped by OCR
    assert not d2.consumer_care_phone.found


def test_consumer_care_phone_prefers_a_real_phone_shape_over_a_bare_licence_number():
    """When a genuine phone-shaped number (a 1800 toll-free, in this case) exists anywhere on
    the label, it must win over an unattributed licence number with no distinguishing context in
    its own OCR region -- exactly the shape of the real deployed-scan failure once the obvious
    keyword/'.No' guards were exhausted."""
    regions = [region("1001206200002"), region("1800 100 1947")]
    d = extract_declarations(regions)
    assert d.consumer_care_phone.found
    assert d.consumer_care_phone.value == "1800 100 1947"


def test_net_quantity_survives_ml_misread_as_mi():
    """Real production bug, found on a live deployed scan (not a hypothetical): Tesseract
    genuinely OCR'd a label's '500 ml' as region.text == '500 mi' (l -> i, a very common single-
    character OCR confusion). NET_QTY_RE's unit whitelist had no tolerance for it, so a plainly
    legible net quantity extracted as "not found" -- confirmed by re-running the exact pipeline
    against the exact uploaded image from the failing deployed scan."""
    regions = [region("Carbonated Drink"), region("500 mi", y=25)]
    d = extract_declarations(regions)
    assert d.net_quantity_value.found
    assert d.net_quantity_value.value == "500"
    assert d.net_quantity_unit.value == "ml"
    assert d.commodity_category == "liquid"


def test_extracts_consumer_care_phone_and_email():
    regions = [region("Consumer Care: 1800-123-4567, help@example.com")]
    d = extract_declarations(regions)
    assert d.consumer_care_phone.found
    assert d.consumer_care_email.found


def test_devanagari_digits_normalized():
    regions = [region("Net Wt. २५० g")]
    d = extract_declarations(regions)
    assert d.net_quantity_value.value == "250"


def test_gujarati_digits_normalized():
    regions = [region("Net Wt. ૨૫૦ g")]
    d = extract_declarations(regions)
    assert d.net_quantity_value.value == "250"


def test_gujarati_digits_normalized_in_mrp():
    """Mirrors the real corruption pattern found via a live Tesseract run against demo_data:
    on tiny (8px) text, the combined eng+hin+guj model misread the Latin digits "25" as the
    Gujarati numerals "૨૬" purely because the combined model has Gujarati digit glyphs in its
    search space (see docs/ARCHITECTURE.md §2 and app/ocr/engine.py _dominant_script). This
    isn't a hypothetical -- confirms the existing digit-normalization path actually converts a
    genuine Gujarati-digit OCR read back to the correct Arabic-numeral MRP value."""
    regions = [region("MRP Rs. ૨૬ incl. of all taxes")]
    d = extract_declarations(regions)
    assert d.mrp_value.value == "26"


def test_image_quality_warning_when_no_text_detected():
    d = extract_declarations([])
    assert d.image_quality_warning is not None
    assert "no text" in d.image_quality_warning.lower()


def test_image_quality_warning_when_sparse_unmatched_text():
    d = extract_declarations([region("xkq7"), region("###")])
    assert d.image_quality_warning is not None


def test_no_image_quality_warning_for_normal_label():
    regions = [
        region("Fresh Valley Snacks", h=40),
        region("Manufactured by Fresh Valley Foods Pvt Ltd, Plot 12, Pune"),
        region("Net Wt. 200 g"),
        region("MRP Rs. 90 incl. of all taxes"),
    ]
    d = extract_declarations(regions)
    assert d.image_quality_warning is None


def test_missing_label_all_fields_absent_and_engine_fails():
    d = extract_declarations([region("Fancy Brand Snacks")])
    report = run_all_checks(d)
    assert report.overall_status == Status.FAIL
    mrp_result = next(r for r in report.results if r.rule_id == "R6-7")
    assert mrp_result.status == Status.FAIL
