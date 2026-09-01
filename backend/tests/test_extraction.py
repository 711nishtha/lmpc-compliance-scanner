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


def test_manufacturer_anchor_tolerates_a_single_character_ocr_misread():
    """Real bug, found from a live deployed scan on a real Maggi retake: OCR read 'Marketed by'
    as 'Matketed by' (a single r->t substitution) and the exact-match anchor correctly, but
    unhelpfully, refused to recognise it -- manufacturer_name came back 'not found' despite being
    legible to a human at a glance. Second independent case this session of one stray character
    breaking an exact match (the first was NET_QTY_RE's 'ml'/'mi' confusion)."""
    regions = [region("Matketed by: Nestle India Limited, 100/101, World Trade Centre")]
    d = extract_declarations(regions)
    assert d.manufacturer_name.found
    assert "Matketed" in d.manufacturer_name.value


def test_fuzzy_matching_recovers_tax_inclusive_wording_from_an_ocr_misread():
    """Second, welcome side-effect of the same fuzzy-matching fix, found while re-verifying the
    local demo baseline: demo_data/03_undersized_mrp_font.png's real OCR text is 'inci. of all
    taxes' (a single l->i misread of 'incl.'). Before fuzzy matching, this was a FALSE FAIL --
    'required wording missing' -- when the wording is almost certainly genuinely printed and
    just misread. Fuzzy tolerance correctly recognises it as the same declaration, downgrading
    to an honest NEEDS_VERIFICATION (low OCR confidence) instead of a false accusation."""
    regions = [region("MRP Rs. 25 inci. of all taxes", conf=48.4)]
    d = extract_declarations(regions)
    assert d.mrp_inclusive_of_taxes_stated.found


def test_fuzzy_anchor_matching_does_not_reopen_the_short_term_collision():
    """Short anchor terms ('rs', 'mrp') must NOT get fuzzy tolerance -- that is exactly how the
    original 'teenagers' substring collision would reappear in a new shape, since almost any
    short word sits within edit-distance-1 of some 2-3 character anchor. Fuzzy matching is
    reserved for long, multi-word phrases only (_FUZZY_MIN_TERM_LEN)."""
    regions = [region("16+17 year old teenagers (ICMR, 2020)")]
    d = extract_declarations(regions)
    assert not d.mrp_value.found


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


def test_net_quantity_still_found_when_ocr_drops_the_net_prefix():
    """Real evidence from a real Nestle Maggi photo re-run through the current pipeline (P1
    investigation): the genuine "NET QUANTITY: 70 g" declaration OCR'd as just 'QUANTITY: +70'
    (psm=12 pass) -- Tesseract dropped the leading "NET" word and the unit entirely, so no
    net_qty anchor term ("net qty"/"net quantity"/"net wt"/...) matched anywhere. Diagnosis: this
    specific real photo's failure is that the unit token itself never survived OCR in the same
    region as the number -- not a fixable extraction-logic bug (fabricating a unit the OCR never
    actually produced would violate this project's "never guess" rule) -- but the anchor-less
    fallback (scan every region for NET_QTY_RE, not just an anchor-matched one) already recovers
    the value correctly whenever a unit IS present, exactly as it should. This test locks in that
    real, load-bearing fallback behaviour so a future "helpful" narrowing of the anchor logic
    can't quietly regress it back to "not found" on labels just like this one."""
    regions = [region("QUANTITY: 70 g")]
    d = extract_declarations(regions)
    assert d.net_quantity_value.found
    assert d.net_quantity_value.value == "70"
    assert d.net_quantity_unit.value == "g"


def test_net_quantity_honestly_not_found_when_ocr_drops_the_unit_too():
    """The other half of the same real Maggi evidence: the ACTUAL OCR text on the real deployed
    photo was 'QUANTITY: +70', with no unit at all surviving next to the number (unlike the
    idealised case above, which still had 'g'). There is no honest way to recover a real value
    here -- guessing "g" because it's the most common unit would be exactly the kind of
    fabricated verdict this project is built to never produce. Correct behaviour is "not found",
    not a lucky-guessed number -- this is what actually ships today, confirmed against the real
    photo re-run live; this test pins it down as a deliberate, tested outcome rather than an
    accidental side effect that could silently flip to fabricating "70g" later."""
    regions = [region("QUANTITY: +70")]
    d = extract_declarations(regions)
    assert not d.net_quantity_value.found


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


# ---------- two-column "label ... value" rows (see fields.py _row_companions) ----------
#
# Regression guards for a real scan of a real product (a DFM/Kurkure packet photographed on a
# table, not a demo mockup). Indian packs print the mandatory declarations as a two-column block
# -- NET QTY. / BATCH NO. / PKD. / USE BY. / MRP down the left, values right-aligned opposite --
# and OCR reads label and value as separate regions. Every geometry below is the ACTUAL measured
# geometry from that scan, not invented numbers. Before this, the scan reported FAIL/"not found"
# for net quantity, MRP and mfg date, all three plainly printed on the pack.


def test_net_quantity_reads_across_a_two_column_label_value_row():
    """Measured geometry: "NET QTY." ends at x=1408, "57" starts at x=1729 (a 321px gutter), and
    the unit "g" is a THIRD separate region at x=1843. The value also sits 25px higher than the
    label that names it. All three must resolve to one declaration."""
    regions = [
        region("INET QTY,", x=1143, y=2472, w=265, h=80, conf=84.5),
        region("57", x=1729, y=2447, w=86, h=64, conf=93.0),
        region("g", x=1843, y=2461, w=37, h=65, conf=92.0),
    ]
    d = extract_declarations(regions)
    assert d.net_quantity_value.value == "57"
    assert d.net_quantity_unit.value == "g"
    assert d.commodity_category == "solid"


def test_stacked_label_value_rows_do_not_steal_each_others_values():
    """The failure mode that made "nearest companion first" necessary rather than just
    concatenating the row. This pack's value column is offset upward by about half a row, so the
    USE BY date (centre y=2785) falls inside the vertical band of the PKD label ABOVE it
    (span 2709-2777) as well as its own. Taking the first regex hit on PKD's whole row reported
    the use-by date as the manufacturing date -- a WRONG value, which is worse than a missing
    one. Each label must take the date nearest to it."""
    regions = [
        region("PKD.", x=1141, y=2709, w=113, h=68, conf=63.0),
        region("7/06/26", x=1747, y=2697, w=172, h=41, conf=60.0),
        region("USE By", x=1140, y=2804, w=209, h=87, conf=78.0),
        region("14/03/27", x=1715, y=2760, w=239, h=50, conf=96.0),
    ]
    d = extract_declarations(regions)
    assert d.mfg_month_year.value == "7/06/26", "PKD must take the date nearest it"
    assert d.best_before_use_by.value == "14/03/27", "USE BY must keep its own date"


def test_row_association_does_not_leap_a_wide_blank_gutter():
    """The row walk chains its gap from region to region, so a row grows through printed content
    but stops at a wide blank -- this is what stops a label reaching across a package fold into
    an unrelated panel. The gap here is far past the limit and there is nothing in between."""
    regions = [
        region("NET QTY.", x=100, y=1000, w=265, h=80),
        region("999 kg", x=3000, y=1000, w=200, h=64),  # different panel entirely
    ]
    d = extract_declarations(regions)
    assert not d.net_quantity_value.found


def test_anchor_survives_one_stray_ocr_letter_welded_onto_it():
    """Real OCR output from that pack: "NET QTY." came back as "INET QTY," -- a stray "I" from
    the printed rule beside it. The exact letter-boundary guard rejects that by design, and so
    does the fuzzy path (it applies the same guard to its window edges)."""
    d = extract_declarations([region("INET QTY, 57 g", w=400, h=80)])
    assert d.net_quantity_value.value == "57"


def test_stray_letter_tolerance_does_not_reopen_the_teenagers_collision():
    """The short-anchor collision the letter-boundary guard exists for must stay closed: "rs" is
    below the length floor for this tolerance, and is preceded by a seven-letter run here anyway."""
    d = extract_declarations([region("16+17 year old teenagers (ICMR, 2020)")])
    assert not d.mrp_value.found


def test_pkd_alone_anchors_the_manufacturing_date():
    """Real packs label the packing date with a bare "PKD.", not "packed on"/"pkd on"."""
    d = extract_declarations([region("PKD. 17/06/26", w=400, h=60)])
    assert d.mfg_month_year.found


def test_full_day_month_year_date_keeps_its_year():
    """DATE_RE alternatives are ordered most-specific-first: Python's `|` is first-match, so the
    short form leading meant a real "14/03/27" extracted as "14/03", silently dropping the year
    and reading as a month/year when it is really a day/month."""
    d = extract_declarations([region("USE BY. 14/03/27", w=400, h=60)])
    assert d.best_before_use_by.value == "14/03/27"
