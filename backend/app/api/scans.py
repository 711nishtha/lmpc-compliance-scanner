from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.rate_limit import enforce_scan_rate_limit
from app.config import (
    ALLOWED_UPLOAD_CONTENT_TYPES,
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    STORAGE_DIR,
)
from app.db import get_db
from app.extraction.fields import extract_declarations, merge_declarations
from app.models.orm import Product, Scan
from app.ocr.engine import OcrUnavailableError, run_ocr
from app.ocr.preprocess import assess_image_quality_floor, cap_dimension, preprocess
from app.reports.annotate import draw_annotations
from app.reports.docx_export import generate_docx_report
from app.reports.pdf import generate_pdf_report
from app.rules.engine import run_all_checks
from app.rules.schema import ComplianceReport

router = APIRouter(prefix="/api/scans", tags=["scans"])

os.makedirs(STORAGE_DIR, exist_ok=True)
REPORTS_DIR = os.path.join(STORAGE_DIR, "..", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


class ScanSummary(BaseModel):
    id: int
    product_name: str
    overall_status: str
    compliance_score: float | None
    created_at: str
    inspector_email: str | None


class ScanDetail(ScanSummary):
    declarations: dict
    rule_results: list[dict]
    ruleset_version: str
    font_size_tier: str


@router.post("", response_model=ScanDetail)
async def create_scan(
    file: UploadFile = File(...),
    product_name: str = Form("Unidentified product"),
    commodity_category: str | None = Form(
        None, description="solid | liquid | count, from product catalog/inspector input — "
        "NOT re-derived from OCR unit text (see extraction/fields.py note on why)."
    ),
    is_imported: bool | None = Form(None),
    is_perishable_category: bool | None = Form(None),
    is_medical_device: bool | None = Form(
        None, description="Medical devices are governed by the Medical Devices Rules, 2017 for "
        "numeral/letter height (Rule 7(2) proviso, G.S.R. 778(E) 23.10.2025) — inspector/catalog "
        "input, never inferred from OCR."
    ),
    reference_width_mm: float | None = Form(None),
    reference_height_mm: float | None = Form(None),
    request: Request = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # OCR is the expensive resource here (~1-3s CPU per scan) — budget it before doing any work.
    enforce_scan_rate_limit(request, user)

    # --- Upload validation: reject before anything reaches the OCR pipeline -------------------
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext and ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            400, f"Unsupported file extension '{ext}'. Allowed: "
                 f"{', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}."
        )
    if file.content_type and file.content_type not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            400, f"Unsupported content type '{file.content_type}'. Upload an image "
                 f"({', '.join(sorted(ALLOWED_UPLOAD_CONTENT_TYPES))})."
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Uploaded file is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image is {len(contents) / 1_048_576:.1f} MB; the limit is "
            f"{MAX_UPLOAD_BYTES / 1_048_576:.0f} MB.",
        )

    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    # Content-type and extension are both client-supplied and trivially spoofed; this decode is
    # the authoritative check that the bytes really are a decodable image.
    if image is None:
        raise HTTPException(400, "Could not decode uploaded image — is it a valid image file?")

    # Quality floor BEFORE cap_dimension/preprocess touch this image -- see assess_image_quality_
    # floor's docstring for why it has to see the image as actually uploaded. A real bug, not a
    # hypothetical: with no floor at all, a 400x250px photo (no OCR engine could plausibly read
    # individual characters at that size) went through the whole pipeline and produced a normal-
    # looking itemized report -- 0% pass, 5 FAILs -- indistinguishable from a genuine finding.
    # Failing this check is a DISTINCT response, not a report: no OCR call, no rule engine, no
    # Scan row written. A bad photo must never be allowed to look like a bad product.
    quality = assess_image_quality_floor(image)
    if not quality.ok:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "IMAGE_QUALITY_INSUFFICIENT",
                "message": quality.reason,
                "shorter_side_px": quality.shorter_side_px,
                "laplacian_variance": round(quality.laplacian_variance, 1),
            },
        )

    # Cap resolution BEFORE anything else touches this image, including writing it to disk.
    # A real phone photo (12MP+) with no cap measurably drove a single request past 350MB RSS
    # once preprocessing, annotation, and Tesseract each held their own full-resolution copy --
    # see app/config.py's MAX_PROCESSING_DIMENSION comment for the measured numbers. Every array
    # derived from `image` from this point on inherits the bound; the stored "original" is a
    # touch smaller than the raw upload but still entirely clear to view, and preprocess() would
    # have capped it internally anyway -- doing it here also means the file written to Render's
    # ephemeral disk is smaller.
    image, _cap_factor = cap_dimension(image)

    scan_uuid = uuid.uuid4().hex
    image_path = os.path.join(STORAGE_DIR, f"{scan_uuid}_original.jpg")
    cv2.imwrite(image_path, image)

    pre = preprocess(image)
    del image  # everything downstream uses pre.final; drop the now-redundant reference
    preprocessed_path = os.path.join(STORAGE_DIR, f"{scan_uuid}_preprocessed.jpg")
    cv2.imwrite(preprocessed_path, pre.final)

    try:
        # Two-pass ensemble, not one call: real product photos (busy, multi-panel, icons
        # interspersed with text) measurably extract more fields correctly under psm=12
        # ("sparse text") than the default psm=3 -- but not uniformly better, field by field, on
        # the same photo (confirmed on 3 real deployed scans: psm=12 gained one field, lost
        # another, on the identical image). merge_declarations() takes the best of both per
        # field rather than betting the whole scan on one page-segmentation mode. Real cost:
        # roughly 2x OCR time versus a single pass -- accepted deliberately, since accuracy on
        # real photography is the more important thing to get right. Placement checks
        # (all_regions, image dimensions) are NOT ensembled -- see merge_declarations()'s
        # docstring -- they use psm=3's region set as the single coherent spatial layout.
        regions_primary = run_ocr(pre.final, psm=3)
        regions_secondary = run_ocr(pre.final, psm=12)
    except OcrUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc

    declarations_primary = extract_declarations(regions_primary)
    declarations_secondary = extract_declarations(regions_secondary)
    declarations = merge_declarations(declarations_primary, declarations_secondary)
    declarations.image_height_px, declarations.image_width_px = pre.final.shape[:2]
    if commodity_category:
        # Overrides the OCR-unit-derived guess -- see extraction/fields.py: inferring category
        # from the very unit text being checked for correctness would make the unit/category
        # mismatch check (R6-4) unable to ever fire. Inspector/catalog input is authoritative.
        declarations.commodity_category = commodity_category
    if is_imported is not None:
        declarations.is_imported = is_imported
    if is_perishable_category is not None:
        declarations.is_perishable_category = is_perishable_category
    if is_medical_device is not None:
        declarations.is_medical_device = is_medical_device

    font_size_tier = "tier1"
    if reference_width_mm and reference_height_mm:
        h, w = pre.final.shape[:2]
        px_per_mm_x = w / reference_width_mm
        px_per_mm_y = h / reference_height_mm
        px_per_mm = (px_per_mm_x + px_per_mm_y) / 2
        declarations.pdp_area_cm2 = (reference_width_mm * reference_height_mm) / 100.0
        declarations.calibration_available = True
        declarations.text_heights_px = {
            k: v / px_per_mm for k, v in declarations.text_heights_px.items()
        }
        font_size_tier = "tier2"

    report: ComplianceReport = run_all_checks(declarations)

    # Bounding boxes on each field's evidence were captured by OCR/extraction but never drawn
    # anywhere (not the live UI, not the PDF/DOCX reports) until this -- found via a real
    # Playwright browser walkthrough, not backend code review. Coordinates are in pre.final's
    # space (that's what run_ocr was given), so annotate that image, not the raw upload.
    annotated = draw_annotations(pre.final, report)
    annotated_path = os.path.join(STORAGE_DIR, f"{scan_uuid}_annotated.jpg")
    cv2.imwrite(annotated_path, annotated)

    product = Product(name=product_name)
    db.add(product)
    db.flush()

    pdf_path = os.path.join(REPORTS_DIR, f"{scan_uuid}.pdf")
    docx_path = os.path.join(REPORTS_DIR, f"{scan_uuid}.docx")
    generate_pdf_report(pdf_path, report, product_name, user["email"], annotated_path, font_size_tier,
                         image_quality_warning=declarations.image_quality_warning)
    generate_docx_report(docx_path, report, product_name, user["email"], font_size_tier,
                          image_quality_warning=declarations.image_quality_warning)

    scan = Scan(
        product_id=product.id,
        inspector_email=user["email"],
        image_path=image_path,
        preprocessed_image_path=preprocessed_path,
        annotated_image_path=annotated_path,
        raw_ocr_json=json.dumps({
            "psm3": [r.__dict__ for r in regions_primary],
            "psm12": [r.__dict__ for r in regions_secondary],
        }),
        declarations_json=declarations.model_dump_json(),
        rule_results_json=json.dumps([r.model_dump(mode="json") for r in report.results]),
        ruleset_version=report.ruleset_version,
        overall_status=report.overall_status.value,
        compliance_score=report.compliance_score,
        font_size_tier=font_size_tier,
        pdf_report_path=pdf_path,
        docx_report_path=docx_path,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    return ScanDetail(
        id=scan.id, product_name=product_name, overall_status=scan.overall_status,
        compliance_score=scan.compliance_score, created_at=scan.created_at.isoformat(),
        inspector_email=scan.inspector_email,
        declarations=json.loads(declarations.model_dump_json()),
        rule_results=json.loads(scan.rule_results_json),
        ruleset_version=scan.ruleset_version, font_size_tier=scan.font_size_tier,
    )


@router.get("", response_model=list[ScanSummary])
def list_scans(
    q: str | None = None,
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = db.query(Scan).join(Product, isouter=True)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if status_filter:
        query = query.filter(Scan.overall_status == status_filter)
    if date_from:
        query = query.filter(Scan.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        # date_to is a bare date (e.g. "2026-08-26") from an <input type=date>, which
        # fromisoformat parses as that day's midnight -- using it directly as an upper bound
        # excludes every scan from later that same day. Found via a real Playwright repository
        # filter test: filtering "today" to "today" returned 0 of 11 scans all created today.
        # Push the bound to the end of that day instead.
        end_of_day = datetime.fromisoformat(date_to) + timedelta(days=1)
        query = query.filter(Scan.created_at < end_of_day)
    scans = query.order_by(Scan.created_at.desc()).all()
    return [
        ScanSummary(
            id=s.id, product_name=s.product.name if s.product else "Unknown",
            overall_status=s.overall_status, compliance_score=s.compliance_score,
            created_at=s.created_at.isoformat(), inspector_email=s.inspector_email,
        )
        for s in scans
    ]


@router.get("/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(404, "Scan not found")
    return ScanDetail(
        id=scan.id, product_name=scan.product.name if scan.product else "Unknown",
        overall_status=scan.overall_status, compliance_score=scan.compliance_score,
        created_at=scan.created_at.isoformat(), inspector_email=scan.inspector_email,
        declarations=json.loads(scan.declarations_json),
        rule_results=json.loads(scan.rule_results_json),
        ruleset_version=scan.ruleset_version, font_size_tier=scan.font_size_tier,
    )


@router.get("/{scan_id}/image")
def get_scan_annotated_image(
    scan_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.annotated_image_path or not os.path.exists(scan.annotated_image_path):
        raise HTTPException(404, "Annotated image not found")
    return FileResponse(scan.annotated_image_path, media_type="image/jpeg")
