"""Rule 7 — Principal Display Panel numeral/letter height checks.

See docs/LEGAL_REQUIREMENTS.md §5. Two tiers, never blended:
  Tier 1 (relative, no calibration) -> always NEEDS_VERIFICATION with a relative-size note.
  Tier 2 (calibrated px-per-mm)     -> hard PASS/FAIL against Table-I below.

A single consolidated Table-I applies regardless of commodity category (weight/volume vs.
length/area/number) -- the original 2011 Rules had a category-dependent Table-I/Table-II split,
but GSR 629(E) dated 23.06.2017 replaced sub-rule (2) with "The height of any numeral and letter
... shall be as per Table-I" and explicitly omitted Table-II. Confirmed against the actual
consolidated Gazette PDF text (not a secondary summary) -- see LEGAL_REQUIREMENTS.md §5 and §9
item 5, which this resolves. An earlier version of this module still implemented the repealed
two-table regime (branching on commodity_category); fixed once the primary text was checked,
found while re-reading the problem statement end to end against the current feature set.
"""
from __future__ import annotations

from .schema import Declarations, Evidence, RuleResult, Status

# Table-I (post-2017, GSR 629(E)): (min_area_cm2_exclusive, max_area_cm2_inclusive) -> mm.
# Applies to every numeral/letter height declaration on the PDP, regardless of commodity category.
TABLE_I = [
    (0, 50, 1.0),
    (50, 100, 1.5),
    (100, 500, 2.5),
    (500, 2500, 4.0),
    (2500, float("inf"), 6.0),
]


def _min_height_mm(area_cm2: float) -> float:
    for lo, hi, mm in TABLE_I:
        if lo < area_cm2 <= hi or (lo == 0 and area_cm2 <= hi):
            return mm
    return TABLE_I[-1][2]


def check_mrp_font_size(d: Declarations) -> RuleResult:
    """R7-1 — Rule 7(2)/Table-I: minimum numeral height for the MRP declaration."""
    return _font_size_check(d, field_key="mrp_value", rule_id="R7-1",
                             label="MRP numeral height")


def check_net_quantity_font_size(d: Declarations) -> RuleResult:
    """R7-2 — Rule 7(2)/Table-I: minimum numeral height for net quantity declaration."""
    return _font_size_check(d, field_key="net_quantity_value", rule_id="R7-2",
                             label="Net quantity numeral height")


def _font_size_check(d: Declarations, field_key: str, rule_id: str, label: str) -> RuleResult:
    ref = "Rule 7(2), Table-I"
    text = (
        "Numeral height for this declaration on the principal display panel must meet the "
        "minimum specified in Rule 7 Table-I, keyed to PDP area."
    )

    # G.S.R. 778(E) dated 23.10.2025 inserted a proviso to Rule 7(2) (and 7(3)): for packages
    # containing medical devices, the Medical Devices Rules, 2017 govern numeral/letter height
    # instead. Table-I therefore does NOT apply, and asserting it would be a wrong citation --
    # so this returns NOT_APPLICABLE with a pointer, never a PASS/FAIL against Table-I.
    # See LEGAL_REQUIREMENTS.md §5.1.
    if d.is_medical_device:
        return RuleResult(
            rule_id=rule_id, rule_reference="Rule 7(2), proviso (G.S.R. 778(E), 23.10.2025)",
            requirement_text=text, status=Status.NOT_APPLICABLE,
            notes=(
                "Package identified as containing a medical device. Rule 7(2)'s proviso (inserted "
                "by G.S.R. 778(E), 23.10.2025) refers numeral/letter height for medical devices to "
                "the Medical Devices Rules, 2017 — Table-I does not apply and this tool does not "
                "implement the MDR 2017 size tables. Verify against MDR 2017 manually."
            ),
        )

    field_heights = d.text_heights_px
    this_height = field_heights.get(field_key)
    ref_height = max(field_heights.values()) if field_heights else None

    if d.calibration_available and d.pdp_area_cm2 is not None and this_height is not None:
        # Tier 2: need px-per-mm, which requires a known reference dimension already baked into
        # text_heights_px by the extraction layer (it stores heights already converted to mm here
        # when calibration_available is True — see extraction/fields.py contract).
        min_mm = _min_height_mm(d.pdp_area_cm2)
        actual_mm = this_height  # already mm-converted upstream when calibrated
        status = Status.PASS if actual_mm >= min_mm else Status.FAIL
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text, status=status,
            evidence=Evidence(extracted_value=f"{actual_mm:.2f} mm (calibrated, Tier 2)"),
            notes=f"{label}: required >= {min_mm} mm for PDP area {d.pdp_area_cm2:.0f} cm^2; measured {actual_mm:.2f} mm.",
        )

    # Tier 1: relative-only, no mm claim possible.
    if this_height is None or ref_height is None or ref_height == 0:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=(
                "No calibration reference and insufficient text-height data to even produce a "
                "relative signal — manual verification required."
            ),
        )
    ratio = this_height / ref_height
    if ratio < 0.35:
        notes = (
            f"Tier 1 (relative, uncalibrated): {label} is only {ratio:.0%} of the tallest text "
            "on the label (typically the brand name) — disproportionately small text is a common "
            "violation pattern, but this is a RELATIVE signal only, not a verified mm measurement "
            "against Rule 7's table. Manual verification with a scale reference required for a "
            "definitive Rule 7 finding."
        )
    else:
        notes = (
            f"Tier 1 (relative, uncalibrated): {label} is {ratio:.0%} of the tallest text on the "
            "label — no obvious disproportion detected, but this is not a calibrated mm "
            "measurement against Rule 7's table. Provide a reference dimension for a Tier 2 "
            "calibrated check."
        )
    return RuleResult(
        rule_id=rule_id, rule_reference=ref, requirement_text=text,
        status=Status.NEEDS_VERIFICATION, notes=notes,
    )


ALL_CHECKS = [check_mrp_font_size, check_net_quantity_font_size]
