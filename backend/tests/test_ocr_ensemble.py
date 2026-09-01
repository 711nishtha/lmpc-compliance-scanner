"""Regression guard for the dual-PSM ensemble: real, measured evidence (not a hypothesis)
that a single Tesseract page-segmentation mode is not enough for busy real-world product
photos. On three real deployed scans (a curved Aldi can, two Maggi retakes), psm=12 found
71-152% more high-confidence OCR words than the default psm=3 -- but field-level testing
showed it was a genuine trade, not a clean win: it gained one declaration and lost another
on the same photo. merge_declarations() takes the best of both per field rather than
betting a whole scan on one segmentation mode. See app/ocr/engine.py's run_ocr() docstring
and app/api/scans.py for the full story and the real numbers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.fields import ExtractedField, merge_declarations
from app.rules.schema import Declarations


def _field(value, conf):
    return ExtractedField(value=value, found=True, ocr_confidence=conf)


def test_merge_prefers_the_pass_that_found_something():
    primary = Declarations()
    secondary = Declarations(consumer_care_email=_field("care@example.com", 80.0))
    merged = merge_declarations(primary, secondary)
    assert merged.consumer_care_email.found
    assert merged.consumer_care_email.value == "care@example.com"


def test_merge_keeps_primary_when_only_primary_found_it():
    primary = Declarations(manufacturer_name=_field("Acme Foods", 90.0))
    secondary = Declarations()
    merged = merge_declarations(primary, secondary)
    assert merged.manufacturer_name.value == "Acme Foods"


def test_merge_prefers_higher_confidence_when_both_found_a_value():
    primary = Declarations(mrp_value=_field("50", 40.0))
    secondary = Declarations(mrp_value=_field("50", 85.0))
    merged = merge_declarations(primary, secondary)
    assert merged.mrp_value.ocr_confidence == 85.0


def test_merge_is_strictly_no_worse_than_either_pass_alone():
    """The real property that matters: the union must never lose a field either pass found on
    its own -- exactly the guarantee that made this worth 2x the OCR time."""
    primary = Declarations(
        manufacturer_name=_field("Nestle India", 70.0),
        consumer_care_email=_field("care@nestle.example.com", 92.0),
    )
    secondary = Declarations(
        manufacturer_name=_field("Nestle India", 45.0),
        mfg_month_year=_field("03/2026", 66.0),
    )
    merged = merge_declarations(primary, secondary)
    assert merged.manufacturer_name.found  # present in both -- must survive
    assert merged.consumer_care_email.found  # only in primary -- must survive
    assert merged.mfg_month_year.found  # only in secondary -- must survive
    assert merged.mfg_month_year.value == "03/2026"


def test_commodity_category_is_rederived_from_the_merged_unit_not_copied_independently():
    """Real bug class this guards against: copying commodity_category independently of
    net_quantity_unit could produce an inconsistent pair (e.g. unit='ml' from secondary,
    category='solid' left over from primary)."""
    primary = Declarations(
        net_quantity_unit=_field("g", 30.0),
        commodity_category="solid",
    )
    secondary = Declarations(net_quantity_unit=_field("ml", 88.0))
    merged = merge_declarations(primary, secondary)
    assert merged.net_quantity_unit.value == "ml"
    assert merged.commodity_category == "liquid"


def test_placement_inputs_are_not_ensembled_come_from_primary_only():
    """all_regions/image dimensions describe ONE coherent photo's spatial layout for R8-1's
    proximity clustering -- mixing two different word-segmentation passes' regions would make
    that incoherent, so these must come from primary only, never merged or overwritten."""
    from app.rules.schema import RegionBox

    primary = Declarations(
        all_regions=[RegionBox(x=0, y=0, width=10, height=10, text="a")],
        image_width_px=1000, image_height_px=800,
    )
    secondary = Declarations(
        all_regions=[RegionBox(x=5, y=5, width=20, height=20, text="b")],
        image_width_px=2000, image_height_px=1600,
    )
    merged = merge_declarations(primary, secondary)
    assert merged.image_width_px == 1000
    assert len(merged.all_regions) == 1
    assert merged.all_regions[0].text == "a"
