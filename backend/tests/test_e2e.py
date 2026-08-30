"""End-to-end pipeline test: OCR-region ground truth -> extraction -> rule engine -> expected
verdicts, for every demo_data mock label (Step 9 gate: each mock label's constructed violation
must actually get flagged the way it was designed to).

Live Tesseract OCR is not installed in this dev environment (see docs/ARCHITECTURE.md §2), so
this test feeds the same OcrRegion objects the real OCR path would produce (per tests/demo_labels.py)
directly into extraction+rules — exercising identical downstream code to the live path, with OCR
itself substituted by fixed ground truth. See README in demo_data/ for what each label tests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PIL import Image

from app.extraction.fields import extract_declarations
from app.rules.engine import run_all_checks
from tests.demo_labels import DEMO_LABELS

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_data"


def _apply_label_metadata(declarations, label):
    # Commodity category is treated as known product-catalog metadata here, not re-derived from
    # the OCR'd unit text -- inferring category from the very unit being checked for correctness
    # would make the liquid-declared-as-count-unit mismatch check unable to ever fire.
    declarations.commodity_category = label.commodity_category
    declarations.is_perishable_category = label.is_perishable_category
    declarations.is_imported = label.is_imported
    # Placement checks (rules/placement.py, R8-1) need the actual image dimensions to normalize
    # distances -- read straight from the rendered PNG rather than duplicating width/height as a
    # separate hardcoded field on DemoLabel, so this can never drift out of sync with the image.
    with Image.open(DEMO_DIR / label.filename) as img:
        declarations.image_width_px, declarations.image_height_px = img.size


@pytest.mark.parametrize("label", DEMO_LABELS, ids=lambda l: l.key)
def test_demo_label_produces_expected_verdicts(label):
    declarations = extract_declarations(label.regions)
    _apply_label_metadata(declarations, label)

    report = run_all_checks(declarations)
    results_by_id = {r.rule_id: r for r in report.results}

    for rule_id, expected_status in label.expected.items():
        actual = results_by_id[rule_id]
        assert actual.status == expected_status, (
            f"{label.key} ({label.filename}): expected {rule_id} = {expected_status}, "
            f"got {actual.status} (notes: {actual.notes!r})"
        )


def test_fully_compliant_label_has_no_hard_fails():
    label = next(l for l in DEMO_LABELS if l.key == "fully_compliant")
    declarations = extract_declarations(label.regions)
    _apply_label_metadata(declarations, label)
    report = run_all_checks(declarations)
    fails = [r for r in report.results if r.status.value == "FAIL"]
    assert not fails, f"Unexpected FAILs on fully-compliant label: {fails}"
