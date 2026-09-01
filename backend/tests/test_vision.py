"""Vision-assisted extraction: the merge policy, and the guarantee that failure is never fatal.

No test here makes a network call. The point of the module under test is that it degrades to
OCR-only on every failure path, so the failure paths are exactly what has to be exercised
offline: no key, HTTP error, timeout, malformed body, wrong schema.
"""
import sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.extraction.fields import merge_vision_into_ocr
from app.rules.schema import BoundingBox, Declarations, ExtractedField
from app.vision import gemini


def _image():
    return np.full((400, 300, 3), 200, dtype=np.uint8)


def _ocr_field(value, box=True):
    return ExtractedField(
        value=value, raw_text_span=value, found=True, ocr_confidence=80.0, source="ocr",
        bounding_box=BoundingBox(x=10, y=20, width=100, height=30) if box else None,
    )


def _vision_field(value):
    return ExtractedField(value=value, raw_text_span=value, found=True, source="vision")


def _gemini_body(payload_json: str):
    return {"candidates": [{"content": {"parts": [{"text": payload_json}]}}]}


def _configured(key="k", enabled=True):
    """Vision switched on for a test. conftest.py disables it globally so no test can reach the
    network by accident; the tests that exercise the transport re-enable it deliberately here,
    against a mocked httpx."""
    stack = ExitStack()
    stack.enter_context(patch.object(gemini, "GEMINI_API_KEY", key))
    stack.enter_context(patch.object(gemini, "VISION_EXTRACTION_ENABLED", enabled))
    return stack


# ---------- merge policy ----------

def test_vision_fills_a_field_ocr_could_not_read():
    """The main reason this pass exists: consumer-care blocks, unit sale prices and tax
    qualifiers that Tesseract cannot resolve on curved or defocused packaging."""
    ocr, vision = Declarations(), Declarations()
    vision.consumer_care_email = _vision_field("care@dfmfoods.com")
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.consumer_care_email.value == "care@dfmfoods.com"
    assert merged.consumer_care_email.source == "vision"


def test_agreement_is_marked_and_keeps_the_ocr_bounding_box():
    """Corroboration is the strongest signal this pipeline can produce -- but the box has to
    survive it, because Rules 7 and 8 measure against real pixel geometry and the vision model
    supplies none."""
    ocr, vision = Declarations(), Declarations()
    ocr.net_quantity_value = _ocr_field("57")
    vision.net_quantity_value = _vision_field("57")
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.net_quantity_value.source == "ocr+vision"
    assert merged.net_quantity_value.bounding_box is not None
    assert merged.net_quantity_value.disagreement_note is None


def test_transcription_style_differences_are_not_treated_as_disagreements():
    """OCR keeps the whole anchor line as the value; the model returns just the value. Same
    declaration, different convention -- reporting that as a conflict would bury real ones."""
    ocr, vision = Declarations(), Declarations()
    ocr.mrp_value = _ocr_field("MRP Rs. 25.00 incl. of all taxes")
    vision.mrp_value = _vision_field("25.00")
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.mrp_value.source == "ocr+vision"


def test_real_disagreement_keeps_the_vision_value_but_discloses_the_ocr_reading():
    """The measured failure mode is OCR mangling a declaration it did locate, so vision wins the
    value -- but an inspection report must not silently discard the losing read."""
    ocr, vision = Declarations(), Declarations()
    ocr.manufacturer_name = _ocr_field("ક Marketed By: DFM Foods Li")
    vision.manufacturer_name = _vision_field(
        "DFM Foods Limited, 149 First Floor, Kilokari, Ring Road, Ashram, New Delhi-110014"
    )
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.manufacturer_name.value.startswith("DFM Foods Limited")
    assert merged.manufacturer_name.source == "vision"
    assert "DFM Foods Li" in merged.manufacturer_name.disagreement_note
    assert merged.manufacturer_name.bounding_box is not None, "OCR geometry must be retained"


def test_ocr_only_fields_are_left_completely_untouched():
    ocr, vision = Declarations(), Declarations()
    ocr.mrp_value = _ocr_field("25.00")
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.mrp_value.source == "ocr"
    assert merged.mrp_value.value == "25.00"


def test_unit_from_vision_still_drives_the_commodity_category():
    """commodity_category is derived from the unit, never copied -- so a unit supplied by the
    vision pass has to re-derive it, or R6-4's unit/category cross-check goes incoherent."""
    ocr, vision = Declarations(), Declarations()
    vision.net_quantity_unit = _vision_field("ml")
    merged = merge_vision_into_ocr(ocr, vision)
    assert merged.commodity_category == "liquid"


# ---------- failure is never fatal ----------

@pytest.mark.parametrize(
    "description,setup",
    [
        ("no api key", lambda: _configured(key="")),
        ("extraction disabled", lambda: _configured(enabled=False)),
    ],
)
def test_disabled_or_unconfigured_returns_none_without_calling_out(description, setup):
    with setup():
        with patch("httpx.post") as post:
            assert gemini.extract_with_gemini(_image()) is None
        post.assert_not_called()


def test_network_error_degrades_to_ocr_only():
    with _configured(), \
         patch("httpx.post", side_effect=OSError("connection refused")):
        assert gemini.extract_with_gemini(_image()) is None


def test_rate_limit_response_degrades_to_ocr_only():
    """429 is the single most likely real failure on a free tier, and it must not fail a scan."""
    class Response:
        status_code = 429
    with _configured(), patch("httpx.post", return_value=Response()):
        assert gemini.extract_with_gemini(_image()) is None


def test_malformed_json_body_degrades_to_ocr_only():
    class Response:
        status_code = 200
        def json(self):
            return _gemini_body("this is not json{{")
    with _configured(), patch("httpx.post", return_value=Response()):
        assert gemini.extract_with_gemini(_image()) is None


def test_unexpected_response_shape_degrades_to_ocr_only():
    class Response:
        status_code = 200
        def json(self):
            return {"unexpected": "shape"}
    with _configured(), patch("httpx.post", return_value=Response()):
        assert gemini.extract_with_gemini(_image()) is None


# ---------- parsing ----------

def test_a_well_formed_response_becomes_declarations():
    body = _gemini_body(
        '{"net_quantity_value": "57", "net_quantity_unit": "g", "mrp_value": "25.00",'
        ' "consumer_care_email": "care@dfmfoods.com", "manufacturer_name": null,'
        ' "country_of_origin": null}'
    )
    class Response:
        status_code = 200
        def json(self):
            return body
    with _configured(), patch("httpx.post", return_value=Response()):
        d = gemini.extract_with_gemini(_image())
    assert d is not None
    assert d.net_quantity_value.value == "57"
    assert d.consumer_care_email.value == "care@dfmfoods.com"
    assert d.net_quantity_value.source == "vision"
    assert not d.manufacturer_name.found, "explicit null must stay 'not found'"
    assert d.net_quantity_value.bounding_box is None, "vision must never invent geometry"


def test_evasive_non_answers_are_treated_as_not_found():
    """A model that says "not visible" instead of returning null must not have that string
    recorded as the printed declaration -- that would read as evidence in the report."""
    body = _gemini_body('{"mrp_value": "not visible", "net_quantity_value": "  "}')
    class Response:
        status_code = 200
        def json(self):
            return body
    with _configured(), patch("httpx.post", return_value=Response()):
        d = gemini.extract_with_gemini(_image())
    assert not d.mrp_value.found
    assert not d.net_quantity_value.found


def test_api_key_is_sent_as_a_header_not_in_the_url():
    """Request URLs land in proxy and server access logs; this one would carry a live credential
    into them."""
    class Response:
        status_code = 200
        def json(self):
            return _gemini_body("{}")
    with _configured("secret-key-value"), \
         patch("httpx.post", return_value=Response()) as post:
        gemini.extract_with_gemini(_image())
    url = post.call_args.args[0]
    assert "secret-key-value" not in url
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "secret-key-value"


# ---------- corroboration reaches the verdict ----------

def test_corroborated_field_is_not_downgraded_by_a_low_ocr_score():
    """Tesseract's confidence runs legitimately low on real packaging (small print, foil glare,
    Devanagari/Gujarati conjuncts -- see ocr/engine.py's reverted confidence floor). A
    declaration the vision pass independently read the SAME way must not still be reported as
    needing manual verification on the strength of that number."""
    from app.rules.mandatory_declarations import check_net_quantity
    from app.rules.schema import Status

    d = Declarations()
    d.net_quantity_value = ExtractedField(
        value="57", found=True, ocr_confidence=31.0, source="ocr+vision",
        bounding_box=BoundingBox(x=10, y=20, width=100, height=30),
    )
    d.net_quantity_unit = ExtractedField(
        value="g", found=True, ocr_confidence=31.0, source="ocr+vision"
    )
    d.commodity_category = "solid"
    assert d.net_quantity_value.low_confidence is False
    assert check_net_quantity(d).status == Status.PASS


def test_an_uncorroborated_low_confidence_field_still_needs_verification():
    """The override is corroboration-specific: a lone low-confidence OCR read is exactly as
    doubtful as it was before the vision pass existed."""
    f = ExtractedField(value="57", found=True, ocr_confidence=31.0, source="ocr")
    assert f.low_confidence is True


def test_a_vision_only_field_is_not_treated_as_low_confidence():
    """It has no Tesseract score to be low. Treating missing as bad would penalise precisely the
    declarations OCR failed to read -- the case the vision pass exists to rescue."""
    f = ExtractedField(value="care@dfmfoods.com", found=True, source="vision")
    assert f.low_confidence is False
