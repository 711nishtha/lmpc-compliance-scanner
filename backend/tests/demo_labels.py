"""Synthetic demo-data label definitions shared by demo_data image generation and test_e2e.py.

Each entry pairs a rendered label image (in demo_data/) with the OCR ground-truth text regions
it was constructed to produce, and the specific rule violation(s) it's meant to exercise. This
lets test_e2e.py validate the full extraction+rule-engine pipeline deterministically without a
live Tesseract install (see docs/ARCHITECTURE.md §2 — Tesseract binary is not installed in this
dev environment) while still exercising exactly the same extraction/rule code the real OCR path
feeds into.

Vertical spacing between lines (85px gaps between y-starts, well beyond any 20-50px line height)
is deliberately generous -- not just for legibility. It's required by R8-2 (Rule 8(1) proviso,
see LEGAL_REQUIREMENTS.md §10.2): the area above/below the net-quantity declaration must be free
of other printed matter by at least the numeral's own height. An earlier, tighter 30px rhythm
left only ~10px of clear space between adjacent lines, which R8-2 correctly flagged as a real
violation on every label including "fully_compliant" -- this is a real bug the new check found
in the demo data itself, the same way the 460px fixed-canvas bug was found in an earlier round
(see scripts/run_real_ocr_pipeline.py history). Fixed by widening the layout, not by weakening
the check.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.extraction.fields import OcrRegion
from app.rules.schema import Status


@dataclass
class DemoLabel:
    key: str
    filename: str
    description: str
    regions: list[OcrRegion]
    commodity_category: str | None
    is_perishable_category: bool | None
    is_imported: bool | None
    expected: dict[str, Status]  # rule_id -> expected status


def _r(text, x, y, w, h, conf=92.0):
    return OcrRegion(text=text, x=x, y=y, width=w, height=h, confidence=conf)


DEMO_LABELS: list[DemoLabel] = [
    DemoLabel(
        key="fully_compliant",
        filename="01_fully_compliant.png",
        description="All Rule 6 declarations present, MRP tax-inclusive, complete consumer care.",
        regions=[
            _r("Fresh Valley Snacks", 20, 20, 300, 40),
            _r("Manufactured by Fresh Valley Foods Pvt Ltd, Plot 12, MIDC, Pune 411018", 20, 110, 350, 20),
            _r("Net Wt. 200 g", 20, 195, 150, 20),
            _r("MRP Rs. 90 incl. of all taxes", 20, 280, 250, 20),
            _r("Mfg Date 03/2026", 20, 365, 150, 20),
            _r("Consumer Care: 1800-123-4567, care@freshvalley.example.com, Pune 411018", 20, 450, 400, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={
            "R6-1": Status.PASS, "R6-3": Status.PASS, "R6-4": Status.PASS,
            "R6-5": Status.PASS, "R6-7": Status.PASS, "R6-9": Status.PASS,
            "R8-1": Status.PASS, "R8-2": Status.PASS,
        },
    ),
    DemoLabel(
        key="missing_mrp",
        filename="02_missing_mrp.png",
        description="Constructed to violate R6-7 (Rule 6(1)(e)) — no MRP declared anywhere on label.",
        regions=[
            _r("Golden Crunch Biscuits", 20, 20, 300, 40),
            _r("Manufactured by Golden Crunch Ltd, Sector 5, Noida 201301", 20, 110, 350, 20),
            _r("Net Wt. 100 g", 20, 195, 150, 20),
            _r("Mfg Date 01/2026", 20, 280, 150, 20),
            _r("Consumer Care: 1800-999-0000", 20, 365, 250, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R6-7": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="undersized_font",
        filename="03_undersized_mrp_font.png",
        description=(
            "Constructed to exercise the Rule 7 Tier-1 relative font-size signal — MRP text "
            "rendered much smaller than the brand name."
        ),
        regions=[
            _r("Royal Spice Masala", 20, 20, 300, 50),  # tall brand text -> height 50
            _r("Manufactured by Royal Spice Co, Indore 452001", 20, 110, 350, 20),
            _r("Net Wt. 50 g", 20, 195, 120, 20),
            _r("MRP Rs. 25 incl. of all taxes", 20, 280, 200, 8),  # tiny height 8 vs brand 50
            _r("Mfg Date 02/2026", 20, 365, 150, 20),
            _r("Consumer Care: help@royalspice.example.com", 20, 450, 250, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R7-1": Status.NEEDS_VERIFICATION, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="missing_consumer_care",
        filename="04_missing_consumer_care.png",
        description="Constructed to violate R6-9 (Rule 6(2)) — no consumer care details at all.",
        regions=[
            _r("Sunrise Cooking Oil", 20, 20, 300, 40),
            _r("Manufactured by Sunrise Oils Pvt Ltd, Rajkot 360001", 20, 110, 350, 20),
            _r("Net Vol. 1 l", 20, 195, 150, 20),
            _r("MRP Rs. 180 incl. of all taxes", 20, 280, 250, 20),
            _r("Mfg Date 04/2026", 20, 365, 150, 20),
        ],
        commodity_category="liquid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R6-9": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="wrong_unit_liquid",
        filename="05_wrong_unit_liquid_as_pieces.png",
        description=(
            "Constructed to violate R6-4 (Rule 6(1)(c)) — a liquid commodity with net quantity "
            "declared in a count unit instead of volume."
        ),
        regions=[
            _r("Clearwater Drinking Water", 20, 20, 300, 40),
            _r("Manufactured by Clearwater Beverages, Chennai 600001", 20, 110, 350, 20),
            _r("Net Qty 12 pieces", 20, 195, 150, 20),
            _r("MRP Rs. 240 incl. of all taxes", 20, 280, 250, 20),
            _r("Mfg Date 05/2026", 20, 365, 150, 20),
            _r("Consumer Care: 1800-555-1212", 20, 450, 250, 20),
        ],
        commodity_category="liquid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R6-4": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="missing_mfg_date",
        filename="06_missing_mfg_date.png",
        description="Constructed to violate R6-5 (Rule 6(1)(d)) — no month/year of manufacture.",
        regions=[
            _r("Mountain Herbal Tea", 20, 20, 300, 40),
            _r("Manufactured by Mountain Herbs Pvt Ltd, Shimla 171001", 20, 110, 350, 20),
            _r("Net Wt. 100 g", 20, 195, 150, 20),
            _r("MRP Rs. 150 incl. of all taxes", 20, 280, 250, 20),
            _r("Consumer Care: 1800-777-8888, care@mountainherbs.example.com", 20, 365, 350, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R6-5": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="imported_missing_country_of_origin",
        filename="07_imported_missing_country_of_origin.png",
        description="Constructed to violate R6-2 (Rule 6(1)(aa)) — imported product with no country-of-origin declaration.",
        regions=[
            _r("Alpine Chocolate Bar", 20, 20, 300, 40),
            _r("Imported by Alpine Imports India, Mumbai 400001", 20, 110, 350, 20),
            _r("Net Wt. 80 g", 20, 195, 150, 20),
            _r("MRP Rs. 220 incl. of all taxes", 20, 280, 250, 20),
            _r("Mfg Date 01/2026", 20, 365, 150, 20),
            _r("Consumer Care: 1800-333-4444", 20, 450, 250, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=True,
        expected={"R6-2": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="missing_manufacturer",
        filename="08_missing_manufacturer.png",
        description="Constructed to violate R6-1 (Rule 6(1)(a)) — no manufacturer/packer/importer name or address.",
        regions=[
            _r("Value Pack Rice", 20, 20, 300, 40),
            _r("Net Wt. 5 kg", 20, 110, 150, 20),
            _r("MRP Rs. 350 incl. of all taxes", 20, 195, 250, 20),
            _r("Mfg Date 06/2026", 20, 280, 150, 20),
            _r("Consumer Care: 1800-222-1111", 20, 365, 250, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={"R6-1": Status.FAIL, "R8-2": Status.PASS},
    ),
    DemoLabel(
        key="hindi_manufacturer_bilingual",
        filename="09_hindi_manufacturer_bilingual.png",
        description=(
            "Real Devanagari (Hindi) script — manufacturer and consumer-care lines in Hindi, "
            "net quantity/MRP/mfg date in English with Arabic numerals (standard Indian retail "
            "label convention). Fully compliant; exercises real-script OCR + anchor matching, "
            "not just the digit-normalization unit test."
        ),
        regions=[
            _r("Mountain Herbal Chai", 20, 20, 300, 40),
            _r("निर्माता: माउंटेन हर्ब्स प्रा. लि., शिमला 171001", 20, 110, 400, 25),
            _r("Net Wt. 100 g", 20, 195, 150, 20),
            _r("MRP Rs. 150 incl. of all taxes", 20, 280, 250, 20),
            _r("Mfg Date 02/2026", 20, 365, 150, 20),
            _r("ग्राहक सेवा: 1800-777-8888, care@mountainherbs.example.com", 20, 450, 450, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={
            "R6-1": Status.PASS, "R6-3": Status.PASS, "R6-4": Status.PASS,
            "R6-5": Status.PASS, "R6-7": Status.PASS, "R6-9": Status.PASS,
            "R8-1": Status.PASS, "R8-2": Status.PASS,
        },
    ),
    DemoLabel(
        key="gujarati_bilingual_liquid",
        filename="10_gujarati_bilingual_liquid.png",
        description=(
            "Real Gujarati script — net quantity, MRP and consumer-care lines in Gujarati "
            "(with Arabic numerals, as standard on real Indian packaging even on vernacular "
            "labels). Fully compliant liquid commodity."
        ),
        regions=[
            _r("Sunrise Cooking Oil", 20, 20, 300, 40),
            _r("Manufactured by Sunrise Oils Pvt Ltd, Rajkot 360001", 20, 110, 380, 20),
            _r("ચોખ્ખો જથ્થો 1000 ml", 20, 195, 220, 20),
            _r("કિંમત રૂ. 180 તમામ કરવેરા સહિત", 20, 280, 320, 20),
            _r("ઉત્પાદન તારીખ 04/2026", 20, 365, 220, 20),
            _r("ગ્રાહક સંભાળ: 1800-555-1212, care@sunriseoils.example.com", 20, 450, 450, 20),
        ],
        commodity_category="liquid",
        is_perishable_category=False,
        is_imported=False,
        expected={
            "R6-1": Status.PASS, "R6-3": Status.PASS, "R6-4": Status.PASS,
            "R6-5": Status.PASS, "R6-7": Status.PASS, "R6-9": Status.PASS,
            "R8-1": Status.PASS, "R8-2": Status.PASS,
        },
    ),
    DemoLabel(
        key="imported_mixed_script_missing_coo",
        filename="11_hindi_gujarati_imported_missing_coo.png",
        description=(
            "Mixed Hindi + Gujarati script, imported product missing country of origin "
            "(violates R6-2). Net quantity line uses a genuine Devanagari numeral (८०, not "
            "OCR-misrecognition-induced) to verify digit normalization on real native-script "
            "digits, not just corrupted Latin ones. Consumer care given in Gujarati with phone "
            "only (no email) to exercise the partial-fields NEEDS_VERIFICATION path (R6-9) on "
            "real script."
        ),
        regions=[
            _r("Alpine Chocolate Bar", 20, 20, 300, 40),
            _r("निर्माता: अल्पाइन इम्पोर्ट्स इंडिया, मुंबई 400001", 20, 110, 400, 25),
            _r("शुद्ध वजन ८० g", 20, 195, 200, 20),
            _r("एम.आर.पी रु. 220 सभी करों सहित", 20, 280, 320, 20),
            _r("निर्माण तिथि 01/2026", 20, 365, 220, 20),
            _r("ગ્રાહક સંભાળ: 1800-333-4444", 20, 450, 280, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=True,
        expected={
            "R6-1": Status.PASS, "R6-2": Status.FAIL, "R6-3": Status.PASS,
            "R6-4": Status.PASS, "R6-5": Status.PASS, "R6-7": Status.PASS,
            "R6-9": Status.NEEDS_VERIFICATION, "R8-2": Status.PASS,
        },
    ),
    DemoLabel(
        key="mrp_placed_far_from_group",
        filename="12_mrp_placed_far_from_group.png",
        description=(
            "Constructed to violate R8-1 (Rule 2(h) + Rule 8(1)) — MRP is placed in an isolated "
            "corner of the image, far from where every other Rule 6 declaration is grouped, "
            "simulating a declaration printed on a different panel of the package instead of "
            "the principal display panel with the rest."
        ),
        regions=[
            _r("Value Deal Detergent Powder", 20, 20, 340, 40),
            _r("Manufactured by Value Deal Chemicals Pvt Ltd, Kanpur 208001", 20, 110, 380, 20),
            _r("Net Wt. 500 g", 20, 195, 150, 20),
            _r("Mfg Date 07/2026", 20, 280, 150, 20),
            _r("Consumer Care: 1800-444-5555, care@valuedeal.example.com", 20, 365, 420, 20),
            # MRP placed far to the right and far below the rest of the cluster -- simulates a
            # separate panel/back-of-pack placement rather than grouped on the PDP with everything
            # else, per Rule 2(h) + Rule 8(1) (LEGAL_REQUIREMENTS.md §10.1).
            _r("MRP Rs. 210 incl. of all taxes", 900, 700, 260, 20),
        ],
        commodity_category="solid",
        is_perishable_category=False,
        is_imported=False,
        expected={
            "R6-1": Status.PASS, "R6-3": Status.PASS, "R6-4": Status.PASS,
            "R6-5": Status.PASS, "R6-7": Status.PASS, "R6-9": Status.PASS,
            "R8-1": Status.FAIL,
        },
    ),
]
