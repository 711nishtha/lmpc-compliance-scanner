"""Typed contract for the compliance rule engine.

Every rule function in this package consumes a Declarations object and returns a RuleResult.
See docs/LEGAL_REQUIREMENTS.md for the checklist each rule_reference below must match.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

RULESET_VERSION = "2026-08-26-draft1"


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class RegionBox(BoundingBox):
    """A bounding box carrying its source OCR text -- used by placement checks
    (rules/placement.py) that need to reason about *all* detected text, not just the subset that
    matched a declaration anchor."""

    text: str = ""


class ExtractedField(BaseModel):
    """A single value pulled from OCR text, with full provenance."""

    value: Optional[str] = None
    raw_text_span: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    ocr_confidence: Optional[float] = Field(
        default=None, description="0-100 Tesseract confidence for the source region"
    )
    language: Optional[str] = Field(default=None, description="eng | hin | guj")
    found: bool = False

    @property
    def low_confidence(self) -> bool:
        return self.ocr_confidence is not None and self.ocr_confidence < 60.0


class Declarations(BaseModel):
    """Structured fields extracted from a package label, per Rule 6."""

    manufacturer_name: ExtractedField = Field(default_factory=ExtractedField)
    manufacturer_address: ExtractedField = Field(default_factory=ExtractedField)
    country_of_origin: ExtractedField = Field(default_factory=ExtractedField)
    common_generic_name: ExtractedField = Field(default_factory=ExtractedField)
    net_quantity_value: ExtractedField = Field(default_factory=ExtractedField)
    net_quantity_unit: ExtractedField = Field(default_factory=ExtractedField)
    mfg_month_year: ExtractedField = Field(default_factory=ExtractedField)
    best_before_use_by: ExtractedField = Field(default_factory=ExtractedField)
    mrp_value: ExtractedField = Field(default_factory=ExtractedField)
    mrp_inclusive_of_taxes_stated: ExtractedField = Field(default_factory=ExtractedField)
    consumer_care_name: ExtractedField = Field(default_factory=ExtractedField)
    consumer_care_address: ExtractedField = Field(default_factory=ExtractedField)
    consumer_care_phone: ExtractedField = Field(default_factory=ExtractedField)
    consumer_care_email: ExtractedField = Field(default_factory=ExtractedField)
    unit_sale_price: ExtractedField = Field(default_factory=ExtractedField)

    # category flags — set by extraction heuristics or manual inspector override
    is_perishable_category: Optional[bool] = None
    is_imported: Optional[bool] = None
    commodity_category: Optional[str] = Field(
        default=None, description="solid | liquid | count | unknown"
    )
    is_combination_or_multipiece_package: Optional[bool] = None
    # G.S.R. 778(E) dated 23.10.2025 carved medical devices out of Rule 7(2)/(3): their numeral
    # and letter heights are governed by the Medical Devices Rules, 2017, not Table-I. Inspector/
    # catalog input, never inferred from OCR text. See LEGAL_REQUIREMENTS.md §5.1.
    is_medical_device: Optional[bool] = None

    # font-size tier inputs
    pdp_area_cm2: Optional[float] = Field(default=None, description="Tier 2 only, if calibrated")
    calibration_available: bool = False
    text_heights_px: dict[str, float] = Field(
        default_factory=dict, description="field_name -> detected text height in px"
    )

    # placement-check inputs (see LEGAL_REQUIREMENTS.md §10, rules/placement.py) — every OCR
    # region (not just the ones that matched a declaration anchor) plus the source image
    # dimensions, so placement checks can reason about proximity/obstruction in the actual photo.
    all_regions: list[RegionBox] = Field(default_factory=list)
    image_width_px: Optional[int] = None
    image_height_px: Optional[int] = None

    # Set by extraction/fields.py's assess_image_quality() when the scanned image itself looks
    # unreadable (very little/no OCR text, or nothing matched any declaration) -- lets the UI show
    # "this looks like a bad photo" instead of letting an all-FAIL report read as "this product
    # fails every rule" when the real story is "OCR couldn't read this image." See §6 in
    # ARCHITECTURE.md's "what is NOT implemented" note this replaces (deferred during frontend QA).
    image_quality_warning: Optional[str] = None


class Evidence(BaseModel):
    extracted_value: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    ocr_confidence: Optional[float] = None
    language: Optional[str] = None


class RuleResult(BaseModel):
    rule_id: str = Field(description="Row id from LEGAL_REQUIREMENTS.md, e.g. R6-1")
    rule_reference: str = Field(description="e.g. 'Rule 6(1)(a)'")
    requirement_text: str
    status: Status
    evidence: Evidence = Field(default_factory=Evidence)
    notes: str = ""


class ComplianceReport(BaseModel):
    ruleset_version: str = RULESET_VERSION
    results: list[RuleResult]

    @property
    def applicable_results(self) -> list[RuleResult]:
        return [r for r in self.results if r.status != Status.NOT_APPLICABLE]

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.applicable_results if r.status == Status.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.applicable_results if r.status == Status.FAIL)

    @property
    def needs_verification_count(self) -> int:
        return sum(
            1 for r in self.applicable_results if r.status == Status.NEEDS_VERIFICATION
        )

    @property
    def compliance_score(self) -> Optional[float]:
        """Secondary summary only — never the primary UI output. See ARCHITECTURE.md §4."""
        total = len(self.applicable_results)
        if total == 0:
            return None
        return round(100.0 * self.pass_count / total, 1)

    @property
    def overall_status(self) -> Status:
        if self.fail_count > 0:
            return Status.FAIL
        if self.needs_verification_count > 0:
            return Status.NEEDS_VERIFICATION
        return Status.PASS
