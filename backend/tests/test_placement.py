"""Unit tests for placement checks (R8-1, R8-2) — see LEGAL_REQUIREMENTS.md §10 and
app/rules/placement.py. Each check gets an explicit PASS and FAIL case, plus the
NEEDS_VERIFICATION paths for missing/insufficient data, matching the discipline in test_rules.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rules import placement as pl
from app.rules.schema import BoundingBox, Declarations, ExtractedField, RegionBox, Status


def field_at(value, x, y, w, h, confidence=90.0):
    return ExtractedField(
        value=value, found=True, ocr_confidence=confidence,
        bounding_box=BoundingBox(x=x, y=y, width=w, height=h),
    )


# ---------- R8-1 grouping on the principal display panel ----------

def _clustered_declarations():
    """All declarations within a tight visual cluster -- same panel."""
    return Declarations(
        manufacturer_name=field_at("Acme Foods", 20, 100, 300, 20),
        common_generic_name=field_at("Snacks", 20, 20, 200, 40),
        net_quantity_value=field_at("200", 20, 180, 100, 20),
        mfg_month_year=field_at("01/2026", 20, 260, 120, 20),
        mrp_value=field_at("90", 20, 340, 150, 20),
        consumer_care_name=field_at("Consumer Care: 123", 20, 420, 300, 20),
        image_width_px=500, image_height_px=500,
    )


def test_grouped_declarations_pass():
    r = pl.check_declarations_grouped_on_pdp(_clustered_declarations())
    assert r.status == Status.PASS
    assert r.rule_id == "R8-1"


def test_outlier_declaration_fails_grouping():
    d = _clustered_declarations()
    # MRP moved far away from the rest of the cluster -- simulates a different panel.
    d.mrp_value = field_at("90", 3000, 3000, 150, 20)
    d.image_width_px, d.image_height_px = 3200, 3200
    r = pl.check_declarations_grouped_on_pdp(d)
    assert r.status == Status.FAIL
    assert "MRP" in r.notes

def test_grouping_needs_verification_with_insufficient_data():
    d = Declarations(mrp_value=field_at("90", 20, 20, 150, 20), image_width_px=500, image_height_px=500)
    r = pl.check_declarations_grouped_on_pdp(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_grouping_needs_verification_without_image_dimensions():
    d = _clustered_declarations()
    d.image_width_px = None
    r = pl.check_declarations_grouped_on_pdp(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_grouping_proxy_disclosed_in_notes():
    r = pl.check_declarations_grouped_on_pdp(_clustered_declarations())
    assert "proxy" in r.notes.lower()


# ---------- R8-2 net-quantity clear space ----------

def test_clear_space_pass_when_unobstructed():
    d = Declarations(
        net_quantity_value=field_at("200", 100, 200, 100, 20),
        all_regions=[
            RegionBox(x=100, y=200, width=100, height=20, text="200 g"),  # the field itself
            RegionBox(x=100, y=0, width=100, height=20, text="Brand Name"),  # far above
            RegionBox(x=100, y=400, width=100, height=20, text="MRP Rs 90"),  # far below
        ],
    )
    r = pl.check_net_quantity_clear_space(d)
    assert r.status == Status.PASS
    assert r.rule_id == "R8-2"


def test_clear_space_fail_when_text_encroaches_above():
    d = Declarations(
        net_quantity_value=field_at("200", 100, 200, 100, 20),
        all_regions=[
            RegionBox(x=100, y=200, width=100, height=20, text="200 g"),
            RegionBox(x=100, y=185, width=200, height=20, text="Manufactured by Acme"),  # 15px above -- inside the 20px buffer
        ],
    )
    r = pl.check_net_quantity_clear_space(d)
    assert r.status == Status.FAIL
    assert "Manufactured by Acme" in r.notes


def test_clear_space_fail_when_text_encroaches_left_right():
    d = Declarations(
        net_quantity_value=field_at("200", 200, 200, 100, 20),
        all_regions=[
            RegionBox(x=200, y=200, width=100, height=20, text="200 g"),
            # Directly to the right, well within the 2x-height horizontal buffer (40px)
            RegionBox(x=310, y=200, width=80, height=20, text="Extra Text"),
        ],
    )
    r = pl.check_net_quantity_clear_space(d)
    assert r.status == Status.FAIL


def test_clear_space_needs_verification_when_net_quantity_not_found():
    d = Declarations()
    r = pl.check_net_quantity_clear_space(d)
    assert r.status == Status.NEEDS_VERIFICATION


def test_clear_space_approximation_disclosed_in_notes():
    d = Declarations(
        net_quantity_value=field_at("200", 100, 200, 100, 20),
        all_regions=[RegionBox(x=100, y=200, width=100, height=20, text="200 g")],
    )
    r = pl.check_net_quantity_clear_space(d)
    assert "approximated" in r.notes.lower() or "conservative" in r.notes.lower()
