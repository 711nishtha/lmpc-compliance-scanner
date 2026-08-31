"""Regression guard for a real bug found on a live deployed scan: OCR hallucinating
Gujarati/Devanagari glyphs on a plain-English label. Found and verified by pulling the actual
uploaded image off the deployed instance and re-running the real pipeline against it -- not
from code review. See app/ocr/engine.py's MIXED_SCRIPT_NOISE_TOLERANCE comment for the full
story, including a word-confidence-floor approach that was tried and reverted after it broke
real Gujarati extraction on demo_data -- see that comment before reaching for a confidence
threshold as a fix here again.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.fields import OcrRegion
from app.ocr.engine import MIN_REFINABLE_ALNUM_CHARS, _dominant_script, _refine_regions_by_script


# ---------- _dominant_script: majority-vote noise tolerance ----------

def test_pure_english_still_classifies_as_eng():
    assert _dominant_script("PRODUCT OF CHINA") == "eng"


def test_pure_gujarati_still_classifies_as_guj():
    assert _dominant_script("ચોખ્ખું વજન") == "guj"


def test_stray_hallucinated_characters_no_longer_veto_the_majority_script():
    """The real bug: a plain-English line the combined model contaminated with a couple of
    hallucinated Gujarati characters must still resolve to 'eng' -- not 'mixed', which would
    send it back to the same combined model that produced the hallucination."""
    # Real Gujarati characters as the noise prefix, matching what was actually observed on the
    # deployed scan: a short hallucinated fragment riding along in front of a clean English line.
    contaminated = "બિ PRODUCT OF CHINA"  # 2 Gujarati chars + a normal English line
    assert _dominant_script(contaminated) == "eng"


def test_genuinely_mixed_content_still_falls_back_to_combined_model():
    """The case this whole design exists for, per engine.py's own docstring: a Hindi phrase
    followed by a Latin email address. Both sides have many characters -- must remain 'mixed',
    not get swallowed by the new noise tolerance."""
    hindi_plus_email = "अधिक जानकारी के लिए संपर्क करें care@example.com"
    assert _dominant_script(hindi_plus_email) == "mixed"


def test_roughly_balanced_two_script_line_stays_mixed():
    """Neither script is an overwhelming majority -- must not be forced to either one."""
    balanced = "ABCDEFGH બિનાક"  # 8 Latin vs 5 Gujarati
    assert _dominant_script(balanced) == "mixed"


def test_gujarati_majority_with_latin_unit_abbreviation_stays_mixed():
    """The regression this asymmetry exists to prevent: a real demo label's genuine Gujarati net-
    quantity line keeps its unit abbreviation in Latin script ('1000 ml') -- extremely common on
    real Indian labels. The tolerance must NOT collapse this to guj-only: a single-script model's
    output alphabet cannot include a different script at all, so guj-only OCR of this crop can
    never produce the Latin 'ml' it needs, no matter how confidently. Must stay 'mixed' so the
    combined model (which reads Latin fine) still gets a chance at it -- confirmed against the
    actual demo_data/10_gujarati_bilingual_liquid.png regression."""
    qty_line = "ચોખ્ખો જથ્થો 1000 ml"  # many Gujarati chars, 2-char Latin unit
    assert _dominant_script(qty_line) == "mixed"


def test_all_digit_line_has_no_script_and_stays_mixed():
    assert _dominant_script("12345 / 67890") == "mixed"


# ---------- _refine_regions_by_script: speed -- skip refinement for too-short regions ----------

def _region(text, x=0, y=0, w=50, h=20, conf=50.0):
    return OcrRegion(text=text, x=x, y=y, width=w, height=h, confidence=conf, language="eng+hin+guj")


def test_short_noise_regions_never_reach_the_second_ocr_call():
    """Real, measured speed bug: on a live deployed scan, 19 of 36 merged regions (53%) were
    two-or-fewer-character noise fragments, each still costing a full second Tesseract subprocess
    call (~167ms average) with zero possible extraction benefit -- see MIN_REFINABLE_ALNUM_CHARS'
    comment. Confirms the expensive path (_ocr_crop, patched here) is never even attempted for
    them, while the region and its first-pass text/confidence survive unchanged."""
    short_regions = [_region("="), _region("७"), _region("io"), _region("A")]
    with patch("app.ocr.engine._ocr_crop") as mock_crop:
        refined = _refine_regions_by_script(None, short_regions, ("eng", "hin", "guj"))
    mock_crop.assert_not_called()
    assert [r.text for r in refined] == [r.text for r in short_regions]


def test_regions_at_or_above_the_char_floor_still_get_refined():
    """The cutoff must not swallow real content -- a region with enough characters to plausibly
    match an anchor or a NET_QTY_RE/MRP_VALUE_RE pattern still goes through refinement."""
    long_region = _region("MRP Rs. 149")  # 9 alnum chars, well above the floor
    assert sum(c.isalnum() for c in long_region.text) >= MIN_REFINABLE_ALNUM_CHARS
    with patch("app.ocr.engine._ocr_crop", return_value=("MRP Rs. 149", 90.0)) as mock_crop, \
         patch("app.ocr.engine._crop_region", return_value=None):
        _refine_regions_by_script(None, [long_region], ("eng", "hin", "guj"))
    mock_crop.assert_called()
