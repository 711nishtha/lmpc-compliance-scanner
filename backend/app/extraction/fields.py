"""Regex + keyword-anchored structured field extraction from OCR output.

This is Step 4 option (a) from the build spec: fully offline, fully explainable, no external
dependency. Each extracted field retains the OCR region it came from for evidence/bounding-box
display in the report. See docs/LEGAL_REQUIREMENTS.md §4 for unit/category rules this must not
contradict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rules.schema import BoundingBox, Declarations, ExtractedField, RegionBox

from .keywords import ALL_ANCHOR_GROUPS


@dataclass
class OcrRegion:
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    language: str = "eng"


NUMBER_RE = r"[\d०-९૦-૯]+(?:[.,]\d+)?"
MRP_VALUE_RE = re.compile(rf"(?:rs\.?|₹|inr)\s*({NUMBER_RE})", re.IGNORECASE)
MRP_VALUE_BARE_RE = re.compile(rf"({NUMBER_RE})\s*(?:/-|only)?", re.IGNORECASE)
# Real bug, found from a live deployed scan: on a real Maggi photo, no genuine "NET QUANTITY:
# 70 g" text survived OCR legibly anywhere, but a completely unrelated noise region --
# "looo290l" (OCR garbage, likely a mangled fragment near a licence/batch number) -- matched
# this pattern and got reported as the net quantity, with "l" satisfying the "litre" unit
# alternative. A genuine printed quantity is essentially always preceded by whitespace, a colon,
# or the start of the region -- not welded directly onto other characters with no separation the
# way "...ooo" is welded onto "290" here. The leading negative lookbehind blocks that: `\W`
# (Python's Unicode-aware word class, which already covers letters AND digits in all three
# supported scripts -- verified directly, not assumed) requires the character immediately before
# the number to be neither a letter nor another digit, i.e. the true start of a fresh token --
# not just "not a letter", which alone still let `re.search` slide one digit later into "90l"
# and match a SUFFIX of the same noise run. A real "1L" bottle label, number directly followed
# by "L", is unaffected -- only what comes BEFORE the number is constrained.
NET_QTY_RE = re.compile(
    rf"(?<!\w)({NUMBER_RE})\s*(g|gm|gms|gram|grams|kg|kilogram|ml|milliliter|l|litre|liter|pcs|pieces|nos)\b",
    re.IGNORECASE,
)
# Alternatives are ordered MOST SPECIFIC FIRST, which is load-bearing rather than cosmetic:
# Python's `|` is first-match, not longest-match, so with the short "\d{1,2}[/-]\d{2,4}" form
# leading, a real full date "14/03/27" matched only its "14/03" prefix and the year was silently
# dropped. That is actively misleading for a Rule 6(1)(d)/(da) declaration -- "14/03" reads as a
# month/year when it is really a day/month -- and it showed up on the first real pack photo
# scanned, whose PKD and USE BY are both printed as dd/mm/yy. The day-first form also allows a
# single leading digit ("7/06/26") because OCR does clip a leading "1" off a date in practice.
DATE_RE = re.compile(
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]{3,9}\s?\d{4}|\d{1,2}[/-]\d{2,4})"
)
PHONE_RE = re.compile(r"(?:\+?91[-\s]?)?\d[\d\-\s]{8,13}\d")
# A tighter, POSITIVE pattern for the two well-known real Indian phone shapes: a 10-digit mobile
# starting 6-9, or a "1800" toll-free number. Real license/batch/registration numbers on Indian
# labels (confirmed against several from a live deployed scan) don't reliably avoid separators --
# one had a single stray internal space -- so "contains a separator" alone isn't a safe positive
# signal; matching a genuine phone SHAPE is. Used as the first, preferred candidate in the
# unanchored fallback scan below; PHONE_RE stays as the last-resort fallback so a real phone in
# an unrecognised format is still better than nothing.
STRICT_PHONE_RE = re.compile(
    r"(?:\+?91[-\s]?)?(?:1800[-\s]?\d{3}[-\s]?\d{3,4}|[6-9]\d{9})\b"
)
# Real bug, found from a live deployed scan: PHONE_RE is purely shape-based (any 10-15 digit
# run) with zero context awareness, so it happily matched an FSSAI/manufacturing licence number
# ("1001202500032", 13 digits) and reported it as the consumer-care phone. Real Indian packaged-
# commodity labels routinely print several long registration/licence/batch numbers near the
# consumer-care block, and any of them is shape-identical to a phone number. Skip a candidate
# region for phone/license purposes if its own text carries one of these explicit non-phone
# numeric-ID markers -- narrowly scoped to what was actually observed and to standard Indian
# label vocabulary, not a guess at every possible false-positive source.
#
# A whole-region keyword list alone was NOT enough, also confirmed on a real deployed scan: OCR
# had dropped the leading "L" from "Lic." leaving "ic No, 1001012000180", which the keyword list
# above does not catch (no "lic" substring survives). Chasing every possible OCR corruption of
# "Lic./Licence/Registration/..." is a losing game. NO_PREFIX_RE instead targets the one
# consistently reliable, general signal: a bare "No"/"No." immediately before a long digit run.
# On real Indian retail labels this is essentially always how a reference/ID number is
# introduced (Lic. No., Batch No., FSSAI No., Order No.) -- a genuine phone number is
# introduced with "Ph:"/"Call:"/"Helpline:"/"Consumer Care:" or given completely bare, never
# with "No." directly in front of it.
NON_PHONE_NUMBER_CONTEXT_RE = re.compile(
    r"\b(lic\.?|licen[cs]e|fssai|reg\.?|regd\.?|registration|batch|lot|gstin|gst)\b",
    re.IGNORECASE,
)
NO_PREFIX_RE = re.compile(r"\bno\.?\s*,?\s*$", re.IGNORECASE)


def _is_reference_number_context(text: str, match: re.Match) -> bool:
    """True if `match` (a PHONE_RE hit) looks like a licence/batch/registration number rather
    than a phone number -- either the whole region carries an explicit marker word, or the
    characters immediately before the match are a bare "No."/"No,"/"No" prefix."""
    if NON_PHONE_NUMBER_CONTEXT_RE.search(text):
        return True
    return bool(NO_PREFIX_RE.search(text[:match.start()]))
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
GUJARATI_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def _normalize_digits(s: str) -> str:
    return s.translate(DEVANAGARI_DIGITS).translate(GUJARATI_DIGITS)


# Real Tesseract misreads confirmed by re-running the actual pipeline against a real deployed
# scan (backend/tests/test_extraction.py::test_ml_ocr_misread_as_mi... captures the exact case):
# a genuine label's "500 ml" was OCR'd as region.text == "500 mi" (lowercase l -> i is one of
# the most common single-character OCR confusions, worse at the resolution real phone photos get
# downscaled to). NET_QTY_RE's unit whitelist had no tolerance for it, so a plainly legible net
# quantity declaration extracted as "not found" -- a false negative on a field a human reads
# instantly. Narrowly scoped and evidence-driven, same discipline as NET_QTY_ANCHORS' own
# docstring: add an entry here only when a REAL OCR run demonstrates the confusion, not
# speculatively. "mi" specifically is safe to always treat as "ml" in this domain -- miles are
# never a valid Legal Metrology net-quantity unit for a packaged commodity.
_UNIT_OCR_MISREADS = {
    r"\bmi\b": "ml",
}


def _normalize_unit_ocr_noise(s: str) -> str:
    for pattern, replacement in _UNIT_OCR_MISREADS.items():
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
    return s


# Real bug, found from a live deployed scan: naive substring containment ("rs" in text_lower)
# matched "teenagers" -- the MRP anchor term "rs" is a substring of "...te**ena**GE**RS**..." --
# and the region containing an unrelated nutrition-disclaimer sentence ("16+17 year old
# teenagers (ICMR, 2020)") got selected as the MRP-anchor region, with "16" extracted as if it
# were a price. A plain \bterm\b word-boundary regex does not fix this cleanly either: \b after a
# term ending in punctuation (e.g. "rs.") requires the following STRING character to be a word
# character for the boundary to fire, so "Rs. 50" (period then space) would fail to match at all.
# Instead: require the characters immediately adjacent to the match are not themselves LETTERS
# (in any of the three supported scripts), regardless of what character the anchor term itself
# starts/ends with. This blocks "rs" matching inside "teenagers" (preceded by the letter "e")
# without breaking "rs." matching "Rs. 50" (followed by a space, not a letter).
#
# Deliberately LETTER-only, not \w (which also excludes digits) -- unlike NET_QTY_RE, anchors
# like "rs"/"₹" legitimately sit directly against a digit in real printed text ("Rs50", "₹50",
# no space). Excluding digit-adjacency too would reject those real matches; only letter-adjacency
# (the actual source of the "teenagers" collision) needs to be blocked here.
_LETTER_CLASS = "A-Za-zऀ-ॿ઀-૿"


def _compile_anchor_terms() -> dict[str, list[tuple[re.Pattern, str]]]:
    compiled: dict[str, list[tuple[re.Pattern, str]]] = {}
    for group, lang_terms in ALL_ANCHOR_GROUPS.items():
        patterns = []
        for terms in lang_terms.values():
            for term in terms:
                patterns.append((
                    re.compile(
                        rf"(?<![{_LETTER_CLASS}]){re.escape(term)}(?![{_LETTER_CLASS}])",
                        re.IGNORECASE,
                    ),
                    term,
                ))
        compiled[group] = patterns
    return compiled


_ANCHOR_PATTERNS = _compile_anchor_terms()

# Real bug, found from a live deployed scan -- and this is the SECOND independent case this
# session of one stray OCR character breaking an exact anchor match (the first was NET_QTY_RE's
# "ml"/"mi" confusion): "Marketed by" was OCR'd as "Matketed by" (a single r->t substitution) on
# a real Maggi photo, and the exact-match anchor above correctly, but unhelpfully, refused to
# recognise it -- manufacturer_name came back "not found" despite the real declaration being
# legible to a human at a glance. Short anchor terms ("rs", "mrp") deliberately do NOT get this
# treatment: fuzzy-matching a 2-3 character term is how the ORIGINAL "teenagers" bug would
# reappear in a new shape (almost any short word is within edit-distance-1 of some 2-3 char
# anchor). Reserved for longer, multi-word phrases where a one-character edit is a small
# fraction of the term and collision risk against unrelated real words is low.
_FUZZY_MIN_TERM_LEN = 10


def _levenshtein_at_most(a: str, b: str, max_dist: int) -> bool:
    """True if edit distance between a and b is <= max_dist. Bails out early once every entry
    in the current DP row exceeds max_dist, since no shorter path can recover from there --
    keeps this cheap even though it runs per anchor-term per region."""
    if abs(len(a) - len(b)) > max_dist:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        if min(cur) > max_dist:
            return False
        prev = cur
    return prev[-1] <= max_dist


def _fuzzy_contains(text: str, term: str, max_dist: int = 1) -> bool:
    """Slides a window of term's length (+/- max_dist, to also tolerate one insertion/deletion)
    across text and accepts if any window is within max_dist edits of term. Windows are checked
    at LETTER-adjacent-safe boundaries only (reusing the same principle as the exact match) so
    this can't match a term as a fuzzy substring of a much longer unrelated word either."""
    text_lower, term_lower = text.lower(), term.lower()
    n = len(term_lower)
    for width in range(max(1, n - max_dist), n + max_dist + 1):
        for start in range(0, len(text_lower) - width + 1):
            end = start + width
            before = text_lower[start - 1] if start > 0 else ""
            after = text_lower[end] if end < len(text_lower) else ""
            if before and before.isalpha() or after and after.isalpha():
                continue
            if _levenshtein_at_most(text_lower[start:end], term_lower, max_dist):
                return True
    return False


# Minimum anchor-term length before a single STRAY ADJACENT LETTER is tolerated -- see
# _term_with_stray_letter. This is the THIRD independent case in this codebase of one spurious
# OCR character defeating an exact anchor match (after "ml"->"mi" and "Marketed"->"Matketed"),
# and the first where the stray character lands OUTSIDE the term instead of inside it: a real
# pack's "NET QTY." came back from OCR as "INET QTY," -- a stray "I" welded onto the front, from
# the printed rule line beside it. Neither existing path could see through that. The exact
# pattern's letter-boundary guard rejects it by design, and the fuzzy path applies the SAME
# guard to its window edges, so it rejects it too.
#
# 5 deliberately excludes the short anchors -- "rs", "mrp", "mfd", "mfg", "pkd", "exp." keep the
# strict boundary. Those are exactly the terms the boundary guard was added for: "rs" tolerating
# one stray letter is how the original "teenagers" false MRP match (see _LETTER_CLASS above)
# would come back. Note it would NOT actually come back even here -- "rs" in "teenagers" is
# preceded by a SEVEN-letter run, not one, so the rule below still rejects it -- but a 2-3
# character term sitting inside real words is too cheap a collision to buy for too little.
_STRAY_LETTER_MIN_TERM_LEN = 5
_MAX_STRAY_ADJACENT_LETTERS = 1


def _letter_run_length(text: str, index: int, step: int) -> int:
    """Length of the unbroken run of letters starting at `index` and walking by `step`."""
    count = 0
    while 0 <= index < len(text) and text[index].isalpha():
        count += 1
        index += step
    return count


def _term_with_stray_letter(text: str, term: str) -> bool:
    """True if `term` appears in `text` bounded by at most one stray letter on either side.

    This is a strictly narrower relaxation than it may look: the letter RUN adjacent to the match
    must be short, so a term buried inside a longer real word is still rejected. "rs" inside
    "teenagers" has a 7-letter run in front of it and fails here exactly as it does under the
    strict guard; "net qty" inside "INET QTY," has a 1-letter run and passes."""
    text_lower, term_lower = text.lower(), term.lower()
    start = text_lower.find(term_lower)
    while start != -1:
        end = start + len(term_lower)
        before = _letter_run_length(text, start - 1, -1)
        after = _letter_run_length(text, end, 1)
        if before <= _MAX_STRAY_ADJACENT_LETTERS and after <= _MAX_STRAY_ADJACENT_LETTERS:
            return True
        start = text_lower.find(term_lower, start + 1)
    return False


def _region_matches_anchor(region: OcrRegion, group: str) -> bool:
    text = region.text
    for pattern, term in _ANCHOR_PATTERNS[group]:
        if pattern.search(text):
            return True
    for _pattern, term in _ANCHOR_PATTERNS[group]:
        if len(term) >= _FUZZY_MIN_TERM_LEN and _fuzzy_contains(text, term):
            return True
    for _pattern, term in _ANCHOR_PATTERNS[group]:
        if len(term) >= _STRAY_LETTER_MIN_TERM_LEN and _term_with_stray_letter(text, term):
            return True
    return False


def _find_anchor_region(regions: list[OcrRegion], group: str) -> OcrRegion | None:
    for region in regions:
        if _region_matches_anchor(region, group):
            return region
    return None


# Two-column "label ... value" association -- see _row_companions for the real bug and the
# measured geometry behind both numbers.
#
# How far above/below the anchor's own vertical span a companion's CENTRE may sit and still count
# as the same printed row, as a multiple of the anchor's height. Real packs do not align a value
# perfectly with its label: measured on the DFM/Kurkure photo, "57" sits 25px ABOVE the baseline
# of the "NET QTY." that labels it, and "17/06/26" 12px above its "PKD.". Centre-in-band rather
# than span-overlap because the label and value are often set in different type sizes (anchor
# heights 68-87px against value heights 41-64px on that pack), which makes a raw overlap
# fraction swing wildly for rows that are obviously the same row to a human reader.
ROW_BAND_TOLERANCE_RATIO = 0.5
# Maximum horizontal whitespace between one region and the next before the row is considered
# broken, as a multiple of the anchor's height. Measured gaps on that pack: 321px for
# "NET QTY." -> "57" (4.0x its 80px anchor) and 493px for "PKD." -> "17/06/26" (7.3x its 68px
# anchor). 8.0 clears both. This is the only thing stopping a row from running off across a
# gutter into an unrelated panel, so it is a real limit, not a formality -- and note the walk
# below chains gaps region-to-region rather than measuring one gap from the anchor, so a row can
# only extend through text, never leap a wide blank gutter.
ROW_MAX_GAP_HEIGHT_RATIO = 8.0


def _row_companions(regions: list[OcrRegion], anchor: OcrRegion) -> list[OcrRegion]:
    """Regions printed on the same visual row as `anchor`, to its right, in reading order.

    Real bug this exists for, found by scanning an actual product photo rather than a demo
    mockup (a DFM/Kurkure packet): Indian packs overwhelmingly print the mandatory declarations
    as a two-column block -- "NET QTY. / BATCH NO. / PKD. / USE BY. / MRP" down the left, their
    values right-aligned opposite. OCR reads those as separate regions, correctly and with high
    confidence ("57" at conf 93, "Rs. 25.00" at conf 95), but _merge_adjacent_words joins words
    into a line only across a gap of ~2.5x text height, so a label never merges with its value
    across the column gutter. Every anchored extraction below then looks for its value INSIDE the
    anchor's own region, finds "NET QTY." alone, and reports the declaration as not found. That
    photo produced FAILs for net quantity, MRP, mfg date and consumer care -- all four plainly
    printed -- and false FAILs are the worst error direction for an enforcement tool.

    Deliberately one-directional (rightward only) and gap-chained: each gap is measured from the
    PREVIOUS region in the row, not from the anchor, so the row grows only through continuous
    printed content and stops dead at the first wide blank. That is what keeps a left-panel
    anchor from reaching across a package's fold into text that has nothing to do with it."""
    if anchor.height <= 0:
        return []
    tolerance = anchor.height * ROW_BAND_TOLERANCE_RATIO
    top = anchor.y - tolerance
    bottom = anchor.y + anchor.height + tolerance
    max_gap = anchor.height * ROW_MAX_GAP_HEIGHT_RATIO

    candidates = sorted(
        (
            r for r in regions
            if r is not anchor
            and r.x >= anchor.x + anchor.width
            and top <= r.y + r.height / 2 <= bottom
        ),
        key=lambda r: r.x,
    )
    companions: list[OcrRegion] = []
    cursor = anchor
    for region in candidates:
        if region.x - (cursor.x + cursor.width) > max_gap:
            break
        companions.append(region)
        cursor = region
    return companions


def _row_text(anchor: OcrRegion, companions: list[OcrRegion]) -> str:
    return " ".join([anchor.text] + [c.text for c in companions])


def _row_region(anchor: OcrRegion, companions: list[OcrRegion]) -> OcrRegion:
    """The anchor and its row companions as one region, so the evidence box drawn on the report
    covers the whole "NET QTY. .... 57 g" row a human would point at, not just the label."""
    if not companions:
        return anchor
    parts = [anchor] + companions
    x = min(p.x for p in parts)
    y = min(p.y for p in parts)
    right = max(p.x + p.width for p in parts)
    bottom = max(p.y + p.height for p in parts)
    return OcrRegion(
        text=_row_text(anchor, companions),
        x=x, y=y, width=right - x, height=bottom - y,
        confidence=min(p.confidence for p in parts),
        language=anchor.language,
    )


def _match_in_anchor_row(
    regions: list[OcrRegion], anchor: OcrRegion | None, matcher
) -> tuple[OcrRegion, re.Match] | None:
    """Finds `matcher`'s value on the anchor's printed row. Returns (evidence region, match).

    Used as a FALLBACK only -- an anchor whose own region already carries its value never gets
    here, so single-column labels behave exactly as before.

    Tries the NEAREST single companion first and only then the whole row concatenated, and both
    stages are load-bearing for a different real case on the same pack:

      * nearest-first is what keeps two stacked label/value rows apart. That pack prints its
        value column offset upward by about half a row, so "14/03/27" (the USE BY date) sits
        vertically inside the band of the "PKD." label above it as well as its own. Concatenating
        PKD's whole row and taking the first regex hit reported the use-by date as the
        manufacturing date -- a wrong value, which for an enforcement tool is worse than the
        missing one it replaced. Ranking by distance from the anchor's centre gives PKD the date
        26px away rather than the one 42px away, and USE BY still gets its own.
      * the concatenated row is what recovers a value OCR split across regions. "57" and its
        unit "g" come back as two separate regions, and NET_QTY_RE needs to see "57 g" together
        -- neither fragment matches alone, so only the joined row text works.

    Evidence is the VALUE side of the row, deliberately NOT the label-plus-value union. That
    union looked friendlier on the report but is actively wrong for Rule 8(1)'s proviso, which
    measures clear space in multiples of the NUMERAL's own size: R8-2 reads this field's bounding
    box, and a box stretched across the column gutter (737px wide for a 151px "57 g" on the pack
    this was built from) inflates the required buffer to something the rule never asks for, which
    manufactures a violation. Pointing at the value keeps the geometry honest, and the value is
    the more useful thing to highlight as evidence anyway."""
    if anchor is None:
        return None
    companions = _row_companions(regions, anchor)
    if not companions:
        return None
    anchor_center = anchor.y + anchor.height / 2
    nearest_first = sorted(
        companions, key=lambda c: abs((c.y + c.height / 2) - anchor_center)
    )
    for companion in nearest_first:
        match = matcher(companion.text)
        if match:
            return companion, match
    match = matcher(_row_text(anchor, companions))
    if match:
        # Matched only once the row was read as a whole (a value OCR split across regions, e.g.
        # "57" and its unit "g"), so the evidence is the value column's own extent -- the
        # companions without the label.
        return _row_region(companions[0], companions[1:]), match
    return None


def _to_extracted_field(region: OcrRegion | None, value: str | None) -> ExtractedField:
    if region is None or value is None:
        return ExtractedField(found=False)
    return ExtractedField(
        value=value,
        raw_text_span=region.text,
        bounding_box=BoundingBox(x=region.x, y=region.y, width=region.width, height=region.height),
        ocr_confidence=region.confidence,
        language=region.language,
        found=True,
    )


def extract_declarations(regions: list[OcrRegion]) -> Declarations:
    d = Declarations()
    full_text = " \n ".join(_normalize_digits(r.text) for r in regions)

    # MRP
    mrp_region = _find_anchor_region(regions, "mrp")
    if mrp_region:
        norm = _normalize_digits(mrp_region.text)
        m = MRP_VALUE_RE.search(norm) or MRP_VALUE_BARE_RE.search(norm)
        if not m:
            # "MRP" in one region, "Rs. 25.00" in the value column -- see _row_companions.
            found = _match_in_anchor_row(
                regions, mrp_region,
                lambda t: MRP_VALUE_RE.search(_normalize_digits(t)),
            )
            if found:
                mrp_region, m = found
        if m:
            d.mrp_value = _to_extracted_field(mrp_region, m.group(1))
    tax_region = _find_anchor_region(regions, "tax_inclusive")
    if tax_region:
        d.mrp_inclusive_of_taxes_stated = _to_extracted_field(tax_region, "yes")

    # Net quantity
    nq_region = _find_anchor_region(regions, "net_qty")
    if nq_region is not None and not NET_QTY_RE.search(
        _normalize_unit_ocr_noise(_normalize_digits(nq_region.text))
    ):
        # "NET QTY." alone in its region, with "57" and even the unit "g" as separate regions in
        # the value column -- all three are one printed row. See _row_companions.
        found = _match_in_anchor_row(
            regions, nq_region,
            lambda t: NET_QTY_RE.search(_normalize_unit_ocr_noise(_normalize_digits(t))),
        )
        if found:
            nq_region = found[0]
    search_regions = [nq_region] if nq_region else regions
    for region in search_regions:
        if region is None:
            continue
        norm = _normalize_unit_ocr_noise(_normalize_digits(region.text))
        m = NET_QTY_RE.search(norm)
        if m:
            d.net_quantity_value = _to_extracted_field(region, m.group(1))
            unit = m.group(2).lower()
            d.net_quantity_unit = _to_extracted_field(region, unit)
            if unit in ("g", "gm", "gms", "gram", "grams", "kg", "kilogram"):
                d.commodity_category = d.commodity_category or "solid"
            elif unit in ("ml", "milliliter", "l", "litre", "liter"):
                d.commodity_category = d.commodity_category or "liquid"
            elif unit in ("pcs", "pieces", "nos"):
                d.commodity_category = d.commodity_category or "count"
            break

    # Mfg date
    mfg_region = _find_anchor_region(regions, "mfg_date")
    if mfg_region:
        norm = _normalize_digits(mfg_region.text)
        m = DATE_RE.search(norm)
        if not m:  # "PKD." labelling a date in the value column -- see _row_companions
            found = _match_in_anchor_row(
                regions, mfg_region, lambda t: DATE_RE.search(_normalize_digits(t))
            )
            if found:
                mfg_region, m = found
        if m:
            d.mfg_month_year = _to_extracted_field(mfg_region, m.group(1))

    # Best before
    bb_region = _find_anchor_region(regions, "best_before")
    if bb_region:
        norm = _normalize_digits(bb_region.text)
        m = DATE_RE.search(norm)
        if not m:  # "USE BY." labelling a date in the value column -- see _row_companions
            found = _match_in_anchor_row(
                regions, bb_region, lambda t: DATE_RE.search(_normalize_digits(t))
            )
            if found:
                bb_region, m = found
        d.best_before_use_by = _to_extracted_field(bb_region, m.group(1) if m else bb_region.text.strip())
        d.is_perishable_category = True

    # Manufacturer
    mfr_region = _find_anchor_region(regions, "manufacturer")
    if mfr_region:
        d.manufacturer_name = _to_extracted_field(mfr_region, mfr_region.text.strip())
        # naive: next region below/adjacent often holds the address; caller may refine
        d.manufacturer_address = _to_extracted_field(mfr_region, mfr_region.text.strip())

    # Country of origin
    coo_region = _find_anchor_region(regions, "country_of_origin")
    if coo_region:
        d.country_of_origin = _to_extracted_field(coo_region, coo_region.text.strip())
        d.is_imported = True

    # Common/generic name: heuristic — largest text region that isn't matched by any anchor group
    anchor_matched_ids = {
        id(r) for group in ALL_ANCHOR_GROUPS for r in regions if _region_matches_anchor(r, group)
    }
    candidates = [r for r in regions if id(r) not in anchor_matched_ids]
    if candidates:
        best = max(candidates, key=lambda r: r.height)
        d.common_generic_name = _to_extracted_field(best, best.text.strip())

    # Consumer care
    cc_region = _find_anchor_region(regions, "consumer_care")
    if cc_region:
        block = cc_region.text
        phone_m = PHONE_RE.search(block)
        if phone_m and _is_reference_number_context(block, phone_m):
            phone_m = None
        email_m = EMAIL_RE.search(block)
        if phone_m:
            d.consumer_care_phone = _to_extracted_field(cc_region, phone_m.group(0))
        if email_m:
            d.consumer_care_email = _to_extracted_field(cc_region, email_m.group(0))
        d.consumer_care_name = _to_extracted_field(cc_region, cc_region.text.strip())
        d.consumer_care_address = _to_extracted_field(cc_region, cc_region.text.strip())
    else:
        # phone/email may appear without an explicit "consumer care" anchor. Deliberately only
        # STRICT_PHONE_RE here, no loose-shape last resort: with no "consumer care" heading to
        # anchor to, a same-region context check (no "No."/keyword left in the OCR'd text) is not
        # always enough to rule out a reference number -- confirmed on a real deployed scan, a
        # bare 13-digit licence number with zero surrounding context in its own merged region
        # slipped past every context check and got reported as a phone. A loose PHONE_RE fallback
        # here would keep confidently asserting a wrong number whenever the real phone simply
        # failed to OCR legibly, rather than correctly reporting "not found" -- and this project's
        # rule throughout is that "not found" beats a fabricated fact. The anchored branch above
        # keeps the looser PHONE_RE because being inside an actual "consumer care" block is real,
        # much stronger context that a same-region digit run really is the phone number.
        for region in regions:
            strict_m = STRICT_PHONE_RE.search(region.text)
            if strict_m and not _is_reference_number_context(region.text, strict_m):
                d.consumer_care_phone = _to_extracted_field(region, strict_m.group(0))
                break

        for region in regions:
            email_m = EMAIL_RE.search(region.text)
            if email_m and not d.consumer_care_email.found:
                d.consumer_care_email = _to_extracted_field(region, email_m.group(0))

    # Unit sale price
    usp_region = _find_anchor_region(regions, "unit_sale_price")
    if usp_region:
        norm = _normalize_digits(usp_region.text)
        m = MRP_VALUE_RE.search(norm) or MRP_VALUE_BARE_RE.search(norm)
        if m:
            d.unit_sale_price = _to_extracted_field(usp_region, m.group(1))

    # Text heights for Tier-1 font-size relative comparison
    for region in regions:
        d.text_heights_px[f"region_{id(region)}"] = region.height
    if d.mrp_value.found and d.mrp_value.bounding_box:
        d.text_heights_px["mrp_value"] = d.mrp_value.bounding_box.height
    if d.net_quantity_value.found and d.net_quantity_value.bounding_box:
        d.text_heights_px["net_quantity_value"] = d.net_quantity_value.bounding_box.height
    if d.common_generic_name.found and d.common_generic_name.bounding_box:
        d.text_heights_px["brand"] = d.common_generic_name.bounding_box.height

    # Every detected text region, for placement checks (LEGAL_REQUIREMENTS.md §10) that need to
    # reason about proximity/obstruction against *all* printed matter, not just matched fields.
    d.all_regions = [
        RegionBox(x=r.x, y=r.y, width=r.width, height=r.height, text=r.text) for r in regions
    ]

    d.image_quality_warning = _assess_image_quality(regions, d)

    _ = full_text  # retained for potential future whole-label heuristics
    return d


_QUALITY_CHECK_FIELDS = (
    # common_generic_name deliberately excluded: it falls back to "tallest unanchored region"
    # unconditionally (see the heuristic above), so it "finds" something even from pure noise --
    # not a genuine signal that any real declaration was recognized.
    "manufacturer_name", "net_quantity_value", "mfg_month_year", "mrp_value", "consumer_care_name",
)


def _assess_image_quality(regions: list[OcrRegion], d: Declarations) -> str | None:
    """Flags when the scan looks unreadable rather than genuinely non-compliant. An all-FAIL
    report can mean either "bad photo" or "bad label", and a viewer (live-demo audience or a real
    inspector) needs to tell which at a glance rather than reading every row's notes -- this was
    deferred during an earlier frontend QA pass (a blank test image produced an honest but
    ambiguous all-FAIL report) and is being closed now. Deliberately conservative: only fires when
    there's essentially nothing to work with, so a real non-compliant label with just a couple of
    legible declarations doesn't trigger a false "unreadable" warning."""
    if not regions:
        return (
            "No text was detected in this image at all. The FAIL results below likely mean the "
            "photo is unreadable (blank, blurry, wrong item, or not a product label) — not that "
            "this product fails every declaration. Retake the photo before treating this as an "
            "enforcement finding."
        )
    found_count = sum(1 for name in _QUALITY_CHECK_FIELDS if getattr(d, name).found)
    if found_count == 0 and len(regions) < 4:
        return (
            f"Only {len(regions)} short text region(s) were detected and none matched a "
            "recognizable declaration. The FAILs below likely reflect a poor-quality or "
            "off-target photo rather than a genuinely non-compliant label — verify with a "
            "clearer photo before treating this as an enforcement finding."
        )
    return None


# Fields that carry OCR provenance (found/value/confidence/bounding box) and are therefore
# safe to merge independently, field by field, between two separate extraction passes.
_MERGEABLE_EXTRACTED_FIELDS = (
    "manufacturer_name", "manufacturer_address", "country_of_origin", "common_generic_name",
    "net_quantity_value", "net_quantity_unit", "mfg_month_year", "best_before_use_by",
    "mrp_value", "mrp_inclusive_of_taxes_stated", "consumer_care_name", "consumer_care_address",
    "consumer_care_phone", "consumer_care_email", "unit_sale_price",
)

_UNIT_TO_CATEGORY = {
    "g": "solid", "gm": "solid", "gms": "solid", "gram": "solid", "grams": "solid",
    "kg": "solid", "kilogram": "solid",
    "ml": "liquid", "milliliter": "liquid", "l": "liquid", "litre": "liquid", "liter": "liquid",
    "pcs": "count", "pieces": "count", "nos": "count",
}


def merge_declarations(primary: Declarations, secondary: Declarations) -> Declarations:
    """Merges two independent extraction passes (e.g. from two different Tesseract page-
    segmentation modes -- see run_ocr()'s psm parameter) into one Declarations object, field by
    field: keep primary's value if it found one; otherwise take secondary's; if BOTH found a
    value for the same field, keep whichever has the higher OCR confidence.

    Deliberately narrow: only the 15 OCR-provenance fields (_MERGEABLE_EXTRACTED_FIELDS) are
    merged this way. Everything else -- is_imported/is_medical_device (inspector input, not
    OCR-derived), all_regions/image dimensions (placement checks reason about ONE photo's
    spatial layout; mixing two different word-segmentation passes' region sets would make R8-1's
    proximity clustering incoherent), and image_quality_warning -- is taken from `primary`
    only, since those describe the image or a single coherent region set, not an individual
    field's value, and have no well-defined per-field merge.

    commodity_category is a special case: it is *inferred from* net_quantity_unit, not an
    independent OCR read, so it is re-derived from whichever unit the merge actually kept
    rather than copied from either input -- copying it independently could produce a
    unit/category pair that don't agree (e.g. unit='ml' from secondary, category='solid'
    left over from primary)."""
    merged = primary.model_copy(deep=True)
    for name in _MERGEABLE_EXTRACTED_FIELDS:
        prim_field, sec_field = getattr(primary, name), getattr(secondary, name)
        if not prim_field.found and sec_field.found:
            setattr(merged, name, sec_field)
        elif prim_field.found and sec_field.found:
            prim_conf = prim_field.ocr_confidence or 0.0
            sec_conf = sec_field.ocr_confidence or 0.0
            if sec_conf > prim_conf:
                setattr(merged, name, sec_field)

    unit = merged.net_quantity_unit.value
    if unit:
        merged.commodity_category = _UNIT_TO_CATEGORY.get(unit.lower(), merged.commodity_category)

    return merged


def _values_agree(ocr_value: str | None, vision_value: str | None) -> bool:
    """Whether two readings of the same declaration are the same declaration.

    Compared loosely on purpose. OCR and a vision model transcribe the same printed text with
    different, equally legitimate conventions -- "Rs. 25.00" against "25.00", "57g" against
    "57 g", "MRP Rs. 25.00 incl. of all taxes" against "25.00" -- and treating those as conflicts
    would fill reports with disagreements that are nothing of the kind. So: normalise away case,
    whitespace and punctuation, then accept if either reading contains the other. Containment
    rather than equality is what handles OCR's habit of keeping the whole anchor line as the
    value while the model returns just the value."""
    if not ocr_value or not vision_value:
        return False
    def norm(text: str) -> str:
        return re.sub(r"[^\w]", "", _normalize_digits(text)).lower()
    a, b = norm(ocr_value), norm(vision_value)
    if not a or not b:
        return False
    return a in b or b in a


def merge_vision_into_ocr(ocr: Declarations, vision: Declarations) -> Declarations:
    """Folds a vision-model read of the label into the OCR result, field by field.

    This is NOT merge_declarations with a different argument: that one merges two Tesseract
    passes, which are the same kind of evidence and are ranked against each other by OCR
    confidence. These two sources are asymmetric and are combined on what each is actually good
    for, not on a confidence number they do not share:

      * OCR alone found it        -> keep it, unchanged.
      * Vision alone found it     -> take it. This is the common case on real packaging and the
                                     main reason the vision pass exists -- consumer-care blocks,
                                     unit sale prices and tax qualifiers that OCR simply cannot
                                     resolve on a curved, glossy or partly-defocused surface.
      * Both, and they AGREE      -> keep OCR's field (it carries the bounding box that Rules 7
                                     and 8 measure against) and mark it "ocr+vision". Two
                                     independent engines reading the same declaration is the
                                     strongest corroboration this pipeline can produce.
      * Both, and they DISAGREE   -> keep the VISION value, keep OCR's BOX, and record what OCR
                                     read in disagreement_note.

    That last rule is the one worth defending. The vision value wins because the measured failure
    mode on real photos is OCR mangling a declaration it did legibly locate ("Marketed By: DFM
    Foods Li", "GS otal Fat (a"), not the reverse. But the disagreement is never thrown away: it
    is carried into the report so an inspector sees both readings and can settle it against the
    physical package. Silently discarding the losing read would make the report state a
    confidence the evidence does not support.

    Geometry is never taken from the vision model -- see gemini._to_field. Fields it supplies
    alone have no bounding box, and the placement/font-size checks already treat a box-less field
    as needing manual verification rather than guessing."""
    merged = ocr.model_copy(deep=True)
    for name in _MERGEABLE_EXTRACTED_FIELDS:
        ocr_field: ExtractedField = getattr(ocr, name)
        vision_field: ExtractedField = getattr(vision, name)
        if not vision_field.found:
            continue
        if not ocr_field.found:
            setattr(merged, name, vision_field.model_copy(deep=True))
            continue
        combined = ocr_field.model_copy(deep=True)
        if _values_agree(ocr_field.value, vision_field.value):
            combined.source = "ocr+vision"
        else:
            combined.value = vision_field.value
            combined.source = "vision"
            combined.disagreement_note = f"OCR read this as {ocr_field.value!r}"
        setattr(merged, name, combined)

    unit = merged.net_quantity_unit.value
    if unit:
        merged.commodity_category = _UNIT_TO_CATEGORY.get(unit.lower(), merged.commodity_category)
    if merged.country_of_origin.found:
        merged.is_imported = True
    return merged
