"""Rule 8 — placement of declarations (LEGAL_REQUIREMENTS.md §10).

Two checks, both derived from real primary-source clause text (not a guessed heuristic):

R8-1 (Rule 2(h) + Rule 8(1) main clause): every Rule 6 declaration must appear on the principal
display panel -- i.e. grouped together in one place, not scattered across the package. There is
no true multi-panel/3D segmentation in this pipeline (one 2D photo in, not an unwrapped package),
so this is a 2D spatial-clustering PROXY for "same panel": declarations whose bounding-box centers
cluster tightly are probably co-located; one far outside that cluster probably isn't. This is
disclosed as a proxy in every result's notes and in the report methodology footer -- never
presented with the same certainty as the presence/correctness checks in mandatory_declarations.py.

R8-2 (Rule 8(1) proviso): the area immediately around the net-quantity declaration must be free of
other printed matter -- at least one numeral-height above/below, two numeral-heights left/right.
Unlike R8-1 this is NOT a proxy: the proviso's own ratio (1x / 2x numeral height) is scale-invariant,
so it needs no calibration and is checked directly against the OCR bounding boxes already produced
by the pipeline. The one approximation: the OCR-merged line box for net quantity may be slightly
taller than the bare numeral glyphs (it includes the unit letters on the same line), which makes
the computed buffer conservative (larger, not smaller) -- disclosed in the result notes.
"""
from __future__ import annotations

import math

from .schema import Declarations, Evidence, ExtractedField, RegionBox, RuleResult, Status

RULE_2H_8_1 = "Rule 2(h), Rule 8(1)"
RULE_8_1_PROVISO = "Rule 8(1), proviso"

# R8-1 thresholds, as a fraction of the image diagonal -- see LEGAL_REQUIREMENTS.md §10.4 and
# tests/test_placement.py for the cases these were chosen against. CLUSTER_PASS_RATIO was
# calibrated at 0.30 against ground-truth coordinates, then found too tight against real
# Tesseract output on demo_data: real generated label images are wide (long single-line
# declarations push canvas width well past its height), which lengthens the diagonal relative to
# the mostly-vertical spread between stacked declarations, so a legitimately tightly-grouped
# label measured ~31-32% instead of the ground-truth-only ~25-28%. Widened to 0.35 -- still a
# clear margin below CLUSTER_FAIL_RATIO, so the deliberate-violation demo label (MRP moved to a
# corner far outside the cluster) still fails correctly. See scripts/run_real_ocr_pipeline.py.
CLUSTER_PASS_RATIO = 0.35
CLUSTER_FAIL_RATIO = 0.45
CLUSTER_FAIL_OUTLIER_MULTIPLE = 2.5


def _grouped_field_boxes(d: Declarations) -> list[tuple[str, ExtractedField]]:
    """The Rule 6 declarations that Rule 8(1) requires to be on the PDP together. One
    representative per logical declaration (consumer-care's 4 sub-fields usually share one OCR
    region, so only one is included to avoid weighting that declaration 4x in the cluster)."""
    candidates: list[tuple[str, ExtractedField]] = [
        ("manufacturer", d.manufacturer_name),
        ("common/generic name", d.common_generic_name),
        ("net quantity", d.net_quantity_value),
        ("mfg date", d.mfg_month_year),
        ("MRP", d.mrp_value),
        ("consumer care", d.consumer_care_name),
    ]
    if d.is_imported:
        candidates.append(("country of origin", d.country_of_origin))
    return [(name, f) for name, f in candidates if f.found and f.bounding_box is not None]


def check_declarations_grouped_on_pdp(d: Declarations) -> RuleResult:
    """R8-1 -- Rule 2(h) + Rule 8(1): all Rule 6 declarations must appear together on the
    principal display panel, not scattered across the package."""
    text = (
        "Every declaration required under Rule 6 must appear on the principal display panel — "
        "i.e. all mandatory declarations must be grouped together in one place, not scattered "
        "across visually separate areas of the package (Rule 2(h) definition + Rule 8(1))."
    )
    proxy_note = (
        "This is a 2D image-plane proximity proxy for \"same panel\" (bounding-box clustering "
        "of detected declarations in the photo), not a certified multi-panel/3D determination — "
        "see LEGAL_REQUIREMENTS.md §10.4."
    )
    boxes = _grouped_field_boxes(d)
    if len(boxes) < 2:
        return RuleResult(
            rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=f"Fewer than 2 declarations located with position data — cannot assess "
                  f"grouping. {proxy_note}",
        )
    if not d.image_width_px or not d.image_height_px:
        return RuleResult(
            rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=f"Image dimensions unavailable — cannot normalize distances. {proxy_note}",
        )
    diagonal = math.hypot(d.image_width_px, d.image_height_px)
    if diagonal == 0:
        return RuleResult(
            rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text,
            status=Status.NEEDS_VERIFICATION, notes=f"Invalid image dimensions. {proxy_note}",
        )

    centers = [
        (name, f.bounding_box.x + f.bounding_box.width / 2, f.bounding_box.y + f.bounding_box.height / 2)
        for name, f in boxes
    ]
    cx = sum(c[1] for c in centers) / len(centers)
    cy = sum(c[2] for c in centers) / len(centers)
    distances = sorted(
        ((name, math.hypot(x - cx, y - cy) / diagonal) for name, x, y in centers),
        key=lambda t: t[1],
    )
    worst_name, worst_ratio = distances[-1]
    median_ratio = distances[len(distances) // 2][1]

    if worst_ratio <= CLUSTER_PASS_RATIO:
        return RuleResult(
            rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text, status=Status.PASS,
            evidence=Evidence(extracted_value=f"max normalized spread {worst_ratio:.0%}"),
            notes=f"All {len(boxes)} located declarations cluster tightly in the image "
                  f"(max distance from centroid: {worst_ratio:.0%} of image diagonal), "
                  f"consistent with a single principal display panel. {proxy_note}",
        )
    is_clear_outlier = worst_ratio > CLUSTER_FAIL_RATIO and (
        median_ratio == 0 or worst_ratio > median_ratio * CLUSTER_FAIL_OUTLIER_MULTIPLE
    )
    if is_clear_outlier:
        return RuleResult(
            rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text, status=Status.FAIL,
            evidence=Evidence(extracted_value=f"{worst_name} at {worst_ratio:.0%} of image diagonal from the rest"),
            notes=f"The '{worst_name}' declaration is positioned far from where the other "
                  f"declarations cluster ({worst_ratio:.0%} of the image diagonal away, vs. a "
                  f"typical spread of {median_ratio:.0%}) — likely not on the same principal "
                  f"display panel as the rest. {proxy_note}",
        )
    return RuleResult(
        rule_id="R8-1", rule_reference=RULE_2H_8_1, requirement_text=text,
        status=Status.NEEDS_VERIFICATION,
        notes=f"'{worst_name}' is somewhat separated from the main cluster of declarations "
              f"({worst_ratio:.0%} of image diagonal) — not clearly a different panel, but not "
              f"clearly the same one either. Manual verification recommended. {proxy_note}",
    )


def check_net_quantity_clear_space(d: Declarations) -> RuleResult:
    """R8-2 -- Rule 8(1) proviso: the area around the net-quantity declaration must be free of
    other printed matter (>= numeral height above/below, >= 2x numeral height left/right)."""
    text = (
        "The area surrounding the net quantity declaration must be free from other printed "
        "information: at least the numeral's own height above and below, and at least twice the "
        "numeral's height to the left and right (Rule 8(1), proviso)."
    )
    approx_note = (
        "Numeral height is approximated from the OCR-merged text line's bounding box (which may "
        "include the unit letters, not just the digits), making the computed buffer conservative "
        "(larger, not smaller) rather than under-strict — see LEGAL_REQUIREMENTS.md §10.4."
    )
    nq = d.net_quantity_value
    if not nq.found or nq.bounding_box is None:
        return RuleResult(
            rule_id="R8-2", rule_reference=RULE_8_1_PROVISO, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=f"Net quantity declaration not located — clear-space compliance cannot be "
                  f"evaluated. {approx_note}",
        )
    box = nq.bounding_box
    h = box.height
    if h <= 0:
        return RuleResult(
            rule_id="R8-2", rule_reference=RULE_8_1_PROVISO, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=f"Invalid numeral height detected. {approx_note}",
        )
    buffer_x0 = box.x - 2 * h
    buffer_x1 = box.x + box.width + 2 * h
    buffer_y0 = box.y - h
    buffer_y1 = box.y + box.height + h

    def _is_same_region(r: RegionBox) -> bool:
        return r.x == box.x and r.y == box.y and r.width == box.width and r.height == box.height

    intruders = []
    for r in d.all_regions:
        if _is_same_region(r):
            continue
        overlaps = not (
            r.x + r.width <= buffer_x0 or r.x >= buffer_x1
            or r.y + r.height <= buffer_y0 or r.y >= buffer_y1
        )
        if overlaps:
            intruders.append(r)

    if not intruders:
        return RuleResult(
            rule_id="R8-2", rule_reference=RULE_8_1_PROVISO, requirement_text=text,
            status=Status.PASS,
            evidence=Evidence(extracted_value=nq.value, bounding_box=box),
            notes=f"No other detected text encroaches on the required clear space around the "
                  f"net quantity declaration. {approx_note}",
        )
    intruder_texts = ", ".join(repr(r.text) for r in intruders[:3])
    return RuleResult(
        rule_id="R8-2", rule_reference=RULE_8_1_PROVISO, requirement_text=text, status=Status.FAIL,
        evidence=Evidence(extracted_value=nq.value, bounding_box=box),
        notes=f"Other printed text encroaches on the required clear space around the net "
              f"quantity declaration: {intruder_texts}. {approx_note}",
    )


ALL_CHECKS = [check_declarations_grouped_on_pdp, check_net_quantity_clear_space]
