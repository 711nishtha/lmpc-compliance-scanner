"""Rule 6 mandatory-declaration checks. Each function = one row of LEGAL_REQUIREMENTS.md §3.

Do not change a threshold or add/remove a check here without updating docs/LEGAL_REQUIREMENTS.md
first — that file is the cited source of truth.
"""
from __future__ import annotations

from .schema import Declarations, Evidence, RuleResult, Status


def _evidence(field) -> Evidence:
    return Evidence(
        extracted_value=field.value,
        bounding_box=field.bounding_box,
        ocr_confidence=field.ocr_confidence,
        language=field.language,
    )


def _found_or_fail(field, rule_id: str, rule_reference: str, requirement_text: str) -> RuleResult:
    if not field.found or not field.value:
        return RuleResult(
            rule_id=rule_id,
            rule_reference=rule_reference,
            requirement_text=requirement_text,
            status=Status.FAIL,
            evidence=_evidence(field),
            notes="Declaration not found on label.",
        )
    notes = "Low OCR confidence — verify manually." if field.low_confidence else ""
    status = Status.NEEDS_VERIFICATION if field.low_confidence else Status.PASS
    return RuleResult(
        rule_id=rule_id,
        rule_reference=rule_reference,
        requirement_text=requirement_text,
        status=status,
        evidence=_evidence(field),
        notes=notes,
    )


def check_manufacturer_details(d: Declarations) -> RuleResult:
    """R6-1 — Rule 6(1)(a): name and address of manufacturer/packer/importer."""
    if not d.manufacturer_name.found and not d.manufacturer_address.found:
        return RuleResult(
            rule_id="R6-1",
            rule_reference="Rule 6(1)(a)",
            requirement_text=(
                "Name and address of the manufacturer, or of the manufacturer and packer if "
                "different, or of the importer, must be declared."
            ),
            status=Status.FAIL,
            notes="Neither manufacturer name nor address found on label.",
        )
    merged_conf = [
        f.ocr_confidence
        for f in (d.manufacturer_name, d.manufacturer_address)
        if f.ocr_confidence is not None
    ]
    low_conf = bool(merged_conf) and min(merged_conf) < 60.0
    missing_part = not d.manufacturer_name.found or not d.manufacturer_address.found
    if missing_part:
        status = Status.NEEDS_VERIFICATION
        notes = "Only partial manufacturer details found (name or address missing) — verify manually."
    elif low_conf:
        status = Status.NEEDS_VERIFICATION
        notes = "Low OCR confidence on manufacturer details — verify manually."
    else:
        status = Status.PASS
        notes = ""
    return RuleResult(
        rule_id="R6-1",
        rule_reference="Rule 6(1)(a)",
        requirement_text=(
            "Name and address of the manufacturer, or of the manufacturer and packer if "
            "different, or of the importer, must be declared."
        ),
        status=status,
        evidence=_evidence(d.manufacturer_name),
        notes=notes,
    )


def check_country_of_origin(d: Declarations) -> RuleResult:
    """R6-2 — Rule 6(1)(aa): country of origin for imported goods.

    Scope for domestic goods is flagged VERIFY WITH DoCA in LEGAL_REQUIREMENTS.md §9 item 1 —
    only evaluated as applicable when is_imported is known True; otherwise NEEDS_VERIFICATION
    rather than guessed.
    """
    rule_id, ref = "R6-2", "Rule 6(1)(aa)"
    text = "Country of origin/manufacture/assembly must be declared for imported products."
    if d.is_imported is False:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.NOT_APPLICABLE, notes="Product identified as domestic.")
    if d.is_imported is None:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes="Import status could not be determined from the label — verify manually.",
        )
    return _found_or_fail(d.country_of_origin, rule_id, ref, text)


def check_common_generic_name(d: Declarations) -> RuleResult:
    """R6-3 — Rule 6(1)(b): common or generic name of the commodity."""
    return _found_or_fail(
        d.common_generic_name, "R6-3", "Rule 6(1)(b)",
        "The common or generic name of the commodity must be declared, plainly and conspicuously.",
    )


def check_net_quantity(d: Declarations) -> RuleResult:
    """R6-4 — Rule 6(1)(c) + Rule 2(f): net quantity in the standard unit of weight/measure/number."""
    rule_id, ref = "R6-4", "Rule 6(1)(c)"
    text = "Net quantity must be declared in the standard unit of weight, measure or number."
    if not d.net_quantity_value.found:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.FAIL, notes="Net quantity value not found on label.")
    if not d.net_quantity_unit.found:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            evidence=_evidence(d.net_quantity_value),
            notes="Net quantity value found but unit not confidently identified — verify manually.",
        )
    # obvious unit/category mismatch check per LEGAL_REQUIREMENTS.md §4
    unit = (d.net_quantity_unit.value or "").strip().lower()
    weight_vol_units = {"g", "kg", "ml", "l", "gm", "gram", "grams", "kilogram", "litre", "liter"}
    count_units = {"pieces", "piece", "pcs", "nos", "no", "count", "units", "unit"}
    if d.commodity_category == "liquid" and unit in count_units:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text, status=Status.FAIL,
            evidence=_evidence(d.net_quantity_value),
            notes=f"Liquid commodity declared in count unit '{unit}' instead of volume — likely non-compliant.",
        )
    if d.commodity_category == "solid" and unit in count_units:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION, evidence=_evidence(d.net_quantity_value),
            notes=f"Solid commodity declared in unit '{unit}' — confirm this is a legitimate count-sold category.",
        )
    _ = weight_vol_units  # reserved for future stricter checks
    conf = d.net_quantity_value.ocr_confidence
    status = Status.NEEDS_VERIFICATION if conf is not None and conf < 60.0 else Status.PASS
    return RuleResult(
        rule_id=rule_id, rule_reference=ref, requirement_text=text, status=status,
        evidence=_evidence(d.net_quantity_value),
        notes="Low OCR confidence — verify manually." if status == Status.NEEDS_VERIFICATION else "",
    )


def check_mfg_month_year(d: Declarations) -> RuleResult:
    """R6-5 — Rule 6(1)(d): month and year of manufacture/pre-packing/import."""
    return _found_or_fail(
        d.mfg_month_year, "R6-5", "Rule 6(1)(d)",
        "Month and year in which the commodity was manufactured, pre-packed or imported must be declared.",
    )


def check_best_before_use_by(d: Declarations) -> RuleResult:
    """R6-6 — Rule 6(1)(da): best-before/use-by date for perishable-category goods only.

    Category list is VERIFY WITH DoCA (LEGAL_REQUIREMENTS.md §9 item 2) — only enforced as
    FAIL when is_perishable_category is confidently True.
    """
    rule_id, ref = "R6-6", "Rule 6(1)(da)"
    text = "Best-before or use-by date must be declared for perishable/shelf-life-limited commodities."
    if d.is_perishable_category is False:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.NOT_APPLICABLE, notes="Commodity not identified as perishable category.")
    if d.is_perishable_category is None:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes="Perishable-category status not determined — verify manually whether this declaration applies.",
        )
    return _found_or_fail(d.best_before_use_by, rule_id, ref, text)


def check_mrp(d: Declarations) -> RuleResult:
    """R6-7 — Rule 6(1)(e): MRP declared, inclusive of all taxes."""
    rule_id, ref = "R6-7", "Rule 6(1)(e)"
    text = "Retail sale price must be declared as MRP, inclusive of all taxes."
    if not d.mrp_value.found:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.FAIL, notes="MRP not found on label.")
    if not d.mrp_inclusive_of_taxes_stated.found:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.FAIL, evidence=_evidence(d.mrp_value),
            notes="MRP found but 'inclusive of all taxes' qualifier not found — required wording missing.",
        )
    conf = d.mrp_value.ocr_confidence
    status = Status.NEEDS_VERIFICATION if conf is not None and conf < 60.0 else Status.PASS
    return RuleResult(
        rule_id=rule_id, rule_reference=ref, requirement_text=text, status=status,
        evidence=_evidence(d.mrp_value),
        notes="Low OCR confidence — verify manually." if status == Status.NEEDS_VERIFICATION else "",
    )


def check_consumer_care(d: Declarations) -> RuleResult:
    """R6-9 — Rule 6(2): consumer care name/address/phone/email.

    Whether all four channels are simultaneously mandatory is VERIFY WITH DoCA
    (LEGAL_REQUIREMENTS.md §9 item 3). We FAIL only if none of the four are found; if some
    but not all are found we return NEEDS_VERIFICATION rather than a hard FAIL/PASS.
    """
    rule_id, ref = "R6-9", "Rule 6(2)"
    text = (
        "Name, address, telephone number and/or e-mail address of a person/office to contact "
        "for consumer complaints must be declared."
    )
    fields = [d.consumer_care_name, d.consumer_care_address, d.consumer_care_phone, d.consumer_care_email]
    found = [f for f in fields if f.found]
    if not found:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.FAIL, notes="No consumer care details found on label.")
    if len(found) < len(fields):
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION, evidence=_evidence(found[0]),
            notes=(
                f"Found {len(found)}/4 consumer-care fields (name/address/phone/email). "
                "Whether all four are simultaneously mandatory is unverified against the primary "
                "source (see LEGAL_REQUIREMENTS.md) — verify manually."
            ),
        )
    return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                       status=Status.PASS, evidence=_evidence(found[0]))


def check_unit_sale_price(d: Declarations) -> RuleResult:
    """R6-10 — Rule 6 (as amended 2023): unit sale price, with 2023-amendment exemptions.

    Not required when MRP == unit sale price (i.e. package net quantity corresponds directly to
    the standard unit) or for combination/group/multi-piece packages.
    """
    rule_id, ref = "R6-10", "Rule 6 (as amended, 2023)"
    text = (
        "Unit sale price (price per standard unit) must be declared, unless it equals the "
        "retail sale price or the package is a combination/group/multi-piece package."
    )
    if d.is_combination_or_multipiece_package:
        return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                           status=Status.NOT_APPLICABLE,
                           notes="Combination/group/multi-piece package — exempt per 2023 amendment.")
    if not d.unit_sale_price.found:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NEEDS_VERIFICATION,
            notes=(
                "Unit sale price not found. Could be exempt (MRP == unit sale price) or missing — "
                "package category not confidently enough determined to auto-FAIL. Verify manually."
            ),
        )
    return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                       status=Status.PASS, evidence=_evidence(d.unit_sale_price))


# Rule 12(6) [VERIFIED-TEXT, confirmed against the consolidated Gazette PDF, same source as
# LEGAL_REQUIREMENTS.md §10]: "The declaration of quantity shall not contain any word or
# expression which tends to create an exaggerated, misleading or inadequate impression as to the
# quantity of the commodity contained in the package, for example, words or expressions like
# 'minimum', 'not less than', 'average', 'about', 'approximately' or other words of a similar
# nature." Directly answers the problem statement's "Detection of missing, misleading or
# non-standard declarations" functional requirement, which nothing else in this module covered —
# found on a full re-read of the PS against the current feature set, not something flagged before.
MISLEADING_QUANTITY_TERMS = [
    "minimum", "min.", "not less than", "average", "about", "approx.", "approximately",
]


def check_quantity_declaration_not_misleading(d: Declarations) -> RuleResult:
    """R6-11 — Rule 12(6): the net quantity declaration must not be qualified by exaggerated,
    misleading or inadequate wording (e.g. 'minimum', 'about', 'approximately')."""
    rule_id, ref = "R6-11", "Rule 12(6)"
    text = (
        "The net quantity declaration must not contain any word or expression that tends to "
        "create an exaggerated, misleading or inadequate impression of quantity (e.g. "
        "'minimum', 'not less than', 'average', 'about', 'approximately')."
    )
    if not d.net_quantity_value.found:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text,
            status=Status.NOT_APPLICABLE,
            notes="Net quantity declaration not located — nothing to check for misleading wording "
                  "(see R6-4 for whether the declaration itself is present).",
        )
    raw = (d.net_quantity_value.raw_text_span or "").lower()
    found_terms = [t for t in MISLEADING_QUANTITY_TERMS if t in raw]
    if found_terms:
        return RuleResult(
            rule_id=rule_id, rule_reference=ref, requirement_text=text, status=Status.FAIL,
            evidence=_evidence(d.net_quantity_value),
            notes=f"Prohibited qualifying word(s) found in the net quantity declaration: "
                  f"{', '.join(found_terms)}.",
        )
    return RuleResult(rule_id=rule_id, rule_reference=ref, requirement_text=text,
                       status=Status.PASS, evidence=_evidence(d.net_quantity_value))


ALL_CHECKS = [
    check_manufacturer_details,
    check_country_of_origin,
    check_common_generic_name,
    check_net_quantity,
    check_mfg_month_year,
    check_best_before_use_by,
    check_mrp,
    check_consumer_care,
    check_unit_sale_price,
    check_quantity_declaration_not_misleading,
]
