"""Second, independent extraction pass over the label photo using Google's Gemini vision model.

WHY THIS EXISTS -- and, just as importantly, what it is NOT allowed to do.

Tesseract has a hard ceiling on real retail packaging, and this project hit it with measurements
rather than opinion. On a real photo of a DFM/Kurkure packet (glossy foil, curved surface, one
panel out of focus) the full OCR pipeline -- after fixing a bogus 30-degree deskew, adding
two-column label/value association, and tolerating stray OCR characters in anchors -- still read
the manufacturer as "Marketed By: DFM Foods Li" (truncated), offered "GS otal Fat (a" as the
commodity's generic name, and found neither the consumer-care block nor the unit sale price,
both plainly printed. Two JPEG re-encodings of the SAME photograph disagreed with each other on
the manufacturing date. That is not a tuning problem; a character-shape recogniser has no way to
know that "GS otal Fat (a" is a nutrition-table fragment rather than a product name.

WHAT IT MAY DO: read the label into the same 15 declaration fields OCR produces, so the two can
be merged field by field (see merge_vision_into_ocr).

WHAT IT MAY NOT DO: decide compliance. Every PASS/FAIL in this system is still produced by the
deterministic, rule-citing engine in app/rules/, from the merged fields. A legal-metrology
finding that cannot be reproduced or traced to a cited rule is not worth having, and a
non-deterministic verdict on the same photograph would be exactly that. The model supplies
EVIDENCE; the rules supply the JUDGEMENT.

FAILURE IS NEVER FATAL. No key, no network, rate-limited, timeout, malformed JSON, unexpected
schema -- every one of these returns None and the scan proceeds on OCR alone, exactly as it did
before this module existed. See extract_with_gemini's contract. This is deliberate: the service
deploys to a free-tier container and gets demonstrated on conference wifi, and a compliance scan
that dies because a third-party API rate-limited it is worse than one that is merely less
accurate.
"""
from __future__ import annotations

import base64
import json
import logging

import cv2
import numpy as np

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MAX_IMAGE_DIMENSION,
    GEMINI_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    VISION_EXTRACTION_ENABLED,
)
from app.rules.schema import Declarations, ExtractedField

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Maps the model's JSON keys to Declarations' field names. Kept explicit rather than derived from
# the Pydantic model: the wire format is a contract with an external service and must not shift
# silently just because a field was renamed internally.
_FIELD_MAP = {
    "manufacturer_name": "manufacturer_name",
    "manufacturer_address": "manufacturer_address",
    "country_of_origin": "country_of_origin",
    "common_generic_name": "common_generic_name",
    "net_quantity_value": "net_quantity_value",
    "net_quantity_unit": "net_quantity_unit",
    "mfg_month_year": "mfg_month_year",
    "best_before_use_by": "best_before_use_by",
    "mrp_value": "mrp_value",
    "mrp_inclusive_of_taxes_stated": "mrp_inclusive_of_taxes_stated",
    "consumer_care_name": "consumer_care_name",
    "consumer_care_address": "consumer_care_address",
    "consumer_care_phone": "consumer_care_phone",
    "consumer_care_email": "consumer_care_email",
    "unit_sale_price": "unit_sale_price",
}

# The prompt's whole job is to stop the model behaving like a helpful assistant. A language model
# asked to "find the MRP" on a label where none is printed will reach for a plausible one, and a
# hallucinated declaration here does not produce a wrong sentence -- it produces a PASS on a
# rule the package actually violates, which is the one failure this tool must never make. Hence:
# transcribe, never infer; null is a valid and expected answer; verbatim text only.
_PROMPT = """You are assisting a Legal Metrology (Packaged Commodities Rules, 2011) inspection in India.

Transcribe the mandatory declarations that are VISIBLY PRINTED on this package label.

ABSOLUTE RULES:
- Transcribe only what is actually printed and legible in the image. Never infer, complete, correct or guess.
- If a declaration is not printed, or you cannot read it clearly, return null for it. null is a normal, expected, CORRECT answer.
- Never substitute a typical or likely value. A wrong value causes a packaged food product to be wrongly cleared or wrongly prosecuted.
- Copy text verbatim, preserving the original script (Latin, Devanagari or Gujarati) exactly as printed.
- Do not translate.

TWO-COLUMN LAYOUTS -- read these carefully, this is where mistakes happen:
Indian packs usually print these declarations as two columns: the labels (NET QTY., BATCH NO., PKD., USE BY., MRP) stacked down the left, and their values right-aligned in a column opposite. The value column is often printed slightly ABOVE the baseline of the label it belongs to. Pair each label with the value on its OWN row, reading straight across. Do not pair a label with the value belonging to the row above or below it.

SANITY CHECK before you answer: a use-by / best-before date is always LATER than the packing / manufacturing date. If your pairing produces a use-by date that is EARLIER than the packing date, you have mis-paired the two columns -- go back and re-read that block.

FIELD NOTES:
- net_quantity_value: the number only (e.g. "57"). net_quantity_unit: the unit only, lowercase (e.g. "g", "ml", "kg", "l", "pcs").
- mrp_value: the numeric amount only, without currency symbols (e.g. "25.00").
- mrp_inclusive_of_taxes_stated: "yes" only if wording such as "inclusive of all taxes" is actually printed; otherwise null.
- mfg_month_year: the date labelled MFD / MFG / PACKED / "PKD.", exactly as printed (e.g. "17/06/26"). This is the EARLIER of the two dates.
- best_before_use_by: the date labelled BEST BEFORE / "USE BY." / EXPIRY, exactly as printed. This is the LATER of the two dates.
- Never report a batch or lot code (e.g. "AYG 114") as a date.
- unit_sale_price: a per-unit price if printed (e.g. "Rs. 0.44/g"), otherwise null.
- country_of_origin: only if explicitly printed as a country of origin/manufacture/import.
- common_generic_name: the generic description of what the commodity IS (e.g. "Ready-to-eat savouries", "Cooking oil"). Never a nutrition-table row, ingredient, brand slogan or marketing phrase.
- consumer_care_*: the complaint/consumer-contact block only, not the manufacturer's own address, unless the label gives the same address for both.

Return ONLY the JSON object described by the schema."""

# responseSchema forces structured output, so parsing never has to strip prose or markdown
# fences. Every field is a nullable string -- including the numeric-looking ones, because the
# printed form ("57", "25.00", "1 000") is the evidence and normalising it is extraction's job,
# not the model's.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {name: {"type": "string", "nullable": True} for name in _FIELD_MAP},
    "required": list(_FIELD_MAP),
}


def vision_extraction_available() -> bool:
    """True if a live call would even be attempted. Lets callers and the report distinguish
    'the model ran and found nothing' from 'the model never ran'."""
    return bool(VISION_EXTRACTION_ENABLED and GEMINI_API_KEY)


def _encode_image(image_bgr: np.ndarray) -> str | None:
    """JPEG-encodes to base64, downscaled first. The image handed to OCR has been upscaled for
    Tesseract's benefit (see preprocess.upscale_if_needed) and can be 3200px on its long side --
    several megabytes of base64 on every scan, for no accuracy gain the model can use."""
    height, width = image_bgr.shape[:2]
    longest = max(height, width)
    if longest > GEMINI_MAX_IMAGE_DIMENSION:
        scale = GEMINI_MAX_IMAGE_DIMENSION / longest
        image_bgr = cv2.resize(
            image_bgr, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA
        )
    ok, buffer = cv2.imencode(".jpg", image_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return None
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def _to_field(value: object) -> ExtractedField:
    """One model answer as an ExtractedField. No bounding box: the model reports content, not
    geometry. Rule 7 (numeral height) and Rule 8 (placement/clear space) need real pixel
    coordinates, so they must keep resting on OCR's boxes -- a plausible-looking box invented
    from a language model would silently corrupt a measurement those rules present as factual.
    Those checks already handle a field with no box by asking for manual verification."""
    if not isinstance(value, str):
        return ExtractedField(found=False)
    text = value.strip()
    if not text or text.lower() in ("null", "none", "n/a", "not printed", "not visible"):
        return ExtractedField(found=False)
    return ExtractedField(value=text, raw_text_span=text, found=True, source="vision")


def _parse_response(payload: dict) -> Declarations | None:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError):
        logger.warning("Gemini response had no usable candidate content; ignoring")
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Gemini response was not valid JSON; ignoring")
        return None
    if not isinstance(data, dict):
        return None

    declarations = Declarations()
    for wire_name, field_name in _FIELD_MAP.items():
        setattr(declarations, field_name, _to_field(data.get(wire_name)))
    if declarations.country_of_origin.found:
        declarations.is_imported = True
    return declarations


def extract_with_gemini(image_bgr: np.ndarray) -> Declarations | None:
    """Reads the label with Gemini and returns a Declarations carrying only field VALUES.

    Returns None -- never raises, and never partially fails -- whenever the model cannot be used
    or cannot be trusted: extraction disabled, no API key, network error, non-200 response,
    timeout, unparseable body. Callers treat None as "OCR only", which is the pipeline's
    behaviour before this module existed. The bare `except Exception` is deliberate and is the
    point of the function: the caller is a compliance scan that must still produce a report, and
    there is no failure mode of a third-party HTTP call worth turning into a 500 here."""
    if not vision_extraction_available():
        return None
    encoded = _encode_image(image_bgr)
    if encoded is None:
        logger.warning("Could not JPEG-encode the image for vision extraction; skipping")
        return None

    request = {
        "contents": [{
            "parts": [
                {"text": _PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": encoded}},
            ]
        }],
        "generationConfig": {
            # Deterministic decoding. The same photograph should not produce a different
            # declaration on a re-scan -- an inspection that cannot be reproduced is not
            # evidence. This does not make the model's output guaranteed-stable, but it removes
            # the sampling variance that is under our control.
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }

    try:
        import httpx

        response = httpx.post(
            GEMINI_ENDPOINT.format(model=GEMINI_MODEL),
            # Key in a header, never in the URL: request URLs end up in proxy and server access
            # logs, and this one would carry a live credential into them.
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json=request,
            timeout=GEMINI_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 -- see docstring: degrade to OCR-only, never 500
        logger.warning("Vision extraction call failed (%s); continuing with OCR only", type(exc).__name__)
        return None

    if response.status_code != 200:
        # Body deliberately not logged: it can echo request content, and this runs on a shared
        # log stream. Status code alone distinguishes the cases that matter (401 key, 429 quota).
        logger.warning(
            "Vision extraction returned HTTP %s; continuing with OCR only", response.status_code
        )
        return None

    try:
        return _parse_response(response.json())
    except Exception as exc:  # noqa: BLE001 -- same contract as above
        logger.warning("Vision response parsing failed (%s); continuing with OCR only", type(exc).__name__)
        return None
