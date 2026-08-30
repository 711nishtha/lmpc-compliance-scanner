"""Unit tests for every rule-engine function: PASS, FAIL, NEEDS_VERIFICATION cases.

Per Step 9 of the build spec, this is a real gate: every rule-engine function must be exercised
against constructed inputs covering all three statuses it can produce.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rules import mandatory_declarations as md
from app.rules import font_size as fs
from app.rules import placement as pl
from app.rules.engine import run_all_checks
from app.rules.schema import Declarations, ExtractedField, Status


def field(value="x", confidence=90.0, found=True):
    return ExtractedField(value=value, ocr_confidence=confidence, found=found)


# ---------- R6-1 manufacturer details ----------

def test_manufacturer_fail_when_absent():
    d = Declarations()
    r = md.check_manufacturer_details(d)
    assert r.status == Status.FAIL


def test_manufacturer_pass_when_complete_high_confidence():
    d = Declarations(manufacturer_name=field(), manufacturer_address=field())
    r = md.check_manufacturer_details(d)
    assert r.status == Status.PASS


def test_manufacturer_needs_verification_when_partial():
    d = Declarations(manufacturer_name=field(), manufacturer_address=ExtractedField())
    r = md.check_manufacturer_details(d)
    assert r.status == Status.NEEDS_VERIFICATION


# ---------- R6-2 country of origin ----------

def test_country_of_origin_not_applicable_when_domestic():
    d = Declarations(is_imported=False)
    r = md.check_country_of_origin(d)
    assert r.status == Status.NOT_APPLICABLE


def test_country_of_origin_needs_verification_when_unknown_import_status():
    d = Declarations(is_imported=None)
    r = md.check_country_of_origin(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_country_of_origin_fail_when_imported_and_missing():
    d = Declarations(is_imported=True)
    r = md.check_country_of_origin(d)
    assert r.status == Status.FAIL


def test_country_of_origin_pass_when_imported_and_present():
    d = Declarations(is_imported=True, country_of_origin=field())
    r = md.check_country_of_origin(d)
    assert r.status == Status.PASS


# ---------- R6-4 net quantity ----------

def test_net_quantity_fail_when_absent():
    r = md.check_net_quantity(Declarations())
    assert r.status == Status.FAIL


def test_net_quantity_needs_verification_when_unit_missing():
    d = Declarations(net_quantity_value=field())
    r = md.check_net_quantity(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_net_quantity_fail_liquid_declared_in_count_unit():
    d = Declarations(
        net_quantity_value=field(),
        net_quantity_unit=field(value="pieces"),
        commodity_category="liquid",
    )
    r = md.check_net_quantity(d)
    assert r.status == Status.FAIL


def test_net_quantity_pass_with_matching_unit():
    d = Declarations(
        net_quantity_value=field(),
        net_quantity_unit=field(value="ml"),
        commodity_category="liquid",
    )
    r = md.check_net_quantity(d)
    assert r.status == Status.PASS


# ---------- R6-6 best-before ----------

def test_best_before_not_applicable_for_non_perishable():
    d = Declarations(is_perishable_category=False)
    r = md.check_best_before_use_by(d)
    assert r.status == Status.NOT_APPLICABLE


def test_best_before_fail_for_perishable_missing():
    d = Declarations(is_perishable_category=True)
    r = md.check_best_before_use_by(d)
    assert r.status == Status.FAIL


def test_best_before_pass_for_perishable_present():
    d = Declarations(is_perishable_category=True, best_before_use_by=field())
    r = md.check_best_before_use_by(d)
    assert r.status == Status.PASS


# ---------- R6-7 MRP ----------

def test_mrp_fail_when_absent():
    r = md.check_mrp(Declarations())
    assert r.status == Status.FAIL


def test_mrp_fail_when_tax_inclusive_wording_missing():
    d = Declarations(mrp_value=field())
    r = md.check_mrp(d)
    assert r.status == Status.FAIL


def test_mrp_pass_when_complete():
    d = Declarations(mrp_value=field(), mrp_inclusive_of_taxes_stated=field())
    r = md.check_mrp(d)
    assert r.status == Status.PASS


# ---------- R6-9 consumer care ----------

def test_consumer_care_fail_when_all_absent():
    r = md.check_consumer_care(Declarations())
    assert r.status == Status.FAIL


def test_consumer_care_needs_verification_when_partial():
    d = Declarations(consumer_care_phone=field())
    r = md.check_consumer_care(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_consumer_care_pass_when_all_four_present():
    d = Declarations(
        consumer_care_name=field(), consumer_care_address=field(),
        consumer_care_phone=field(), consumer_care_email=field(),
    )
    r = md.check_consumer_care(d)
    assert r.status == Status.PASS


# ---------- R6-10 unit sale price ----------

def test_unit_sale_price_not_applicable_for_multipiece():
    d = Declarations(is_combination_or_multipiece_package=True)
    r = md.check_unit_sale_price(d)
    assert r.status == Status.NOT_APPLICABLE


def test_unit_sale_price_needs_verification_when_missing():
    d = Declarations(is_combination_or_multipiece_package=False)
    r = md.check_unit_sale_price(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_unit_sale_price_pass_when_present():
    d = Declarations(unit_sale_price=field())
    r = md.check_unit_sale_price(d)
    assert r.status == Status.PASS


# ---------- R6-11 net quantity declaration not misleading ----------

def test_misleading_quantity_not_applicable_when_quantity_absent():
    d = Declarations()
    r = md.check_quantity_declaration_not_misleading(d)
    assert r.status == Status.NOT_APPLICABLE


def test_misleading_quantity_pass_when_clean():
    d = Declarations(net_quantity_value=ExtractedField(
        value="200", found=True, raw_text_span="Net Wt. 200 g",
    ))
    r = md.check_quantity_declaration_not_misleading(d)
    assert r.status == Status.PASS


def test_misleading_quantity_fail_when_qualifying_word_present():
    d = Declarations(net_quantity_value=ExtractedField(
        value="200", found=True, raw_text_span="Net Wt. approximately 200 g",
    ))
    r = md.check_quantity_declaration_not_misleading(d)
    assert r.status == Status.FAIL
    assert "approximately" in r.notes


# ---------- Rule 7 font size ----------

def test_font_size_needs_verification_without_calibration():
    d = Declarations(text_heights_px={"mrp_value": 5, "brand": 40})
    r = fs.check_mrp_font_size(d)
    assert r.status == Status.NEEDS_VERIFICATION
    assert "Tier 1" in r.notes


def test_font_size_needs_verification_with_no_height_data():
    r = fs.check_mrp_font_size(Declarations())
    assert r.status == Status.NEEDS_VERIFICATION


def test_font_size_tier2_fail_below_threshold():
    d = Declarations(
        calibration_available=True, pdp_area_cm2=80, commodity_category="solid",
        text_heights_px={"mrp_value": 1.0},  # below 1.5mm required for 50-100 cm^2
    )
    r = fs.check_mrp_font_size(d)
    assert r.status == Status.FAIL
    assert "Tier 2" in (r.evidence.extracted_value or "")


def test_font_size_tier2_pass_above_threshold():
    d = Declarations(
        calibration_available=True, pdp_area_cm2=80, commodity_category="solid",
        text_heights_px={"mrp_value": 2.0},
    )
    r = fs.check_mrp_font_size(d)
    assert r.status == Status.PASS


# ---------- engine ----------

# ---------- R7 medical-device carve-out (G.S.R. 778(E), 23.10.2025) ----------

def test_font_size_not_applicable_for_medical_device():
    """Rule 7(2)'s proviso refers medical devices to the Medical Devices Rules, 2017 — Table-I
    must NOT be asserted against them. Regression guard for a real gap found on the full
    primary-source pass (see LEGAL_REQUIREMENTS.md §5.1)."""
    d = Declarations(
        is_medical_device=True,
        pdp_area_cm2=120.0,
        calibration_available=True,
        text_heights_px={"mrp_value": 0.5, "brand": 10.0},  # would FAIL Table-I if applied
    )
    r = fs.check_mrp_font_size(d)
    assert r.status == Status.NOT_APPLICABLE
    assert "Medical Devices Rules, 2017" in r.notes
    assert "778" in r.rule_reference


def test_font_size_still_applies_when_not_medical_device():
    d = Declarations(
        is_medical_device=False,
        pdp_area_cm2=120.0,
        calibration_available=True,
        text_heights_px={"mrp_value": 0.5, "brand": 10.0},
    )
    r = fs.check_mrp_font_size(d)
    assert r.status == Status.FAIL  # 0.5mm < 2.5mm required for 100-500 cm2


def test_engine_runs_all_checks_and_aggregates():
    d = Declarations()
    report = run_all_checks(d)
    assert len(report.results) == len(md.ALL_CHECKS) + len(fs.ALL_CHECKS) + len(pl.ALL_CHECKS)
    assert report.overall_status == Status.FAIL  # everything empty -> FAILs dominate
    assert report.compliance_score is not None
