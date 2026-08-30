"""Itemized, rule-cited PDF compliance report (ReportLab).

Primary output is the itemized checklist, not a bare score — see ARCHITECTURE.md §4/§7.
"""
from __future__ import annotations

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.rules.schema import ComplianceReport, Status

# MIRRORS frontend/src/tokens.css --color-status-* (and annotate.py STATUS_BGR).
# Keep all three in sync or the PDF contradicts the UI and the annotated image.
STATUS_COLORS = {
    Status.PASS: colors.HexColor("#2E5A3B"),
    Status.FAIL: colors.HexColor("#A63A2B"),
    Status.NEEDS_VERIFICATION: colors.HexColor("#8A6114"),
    Status.NOT_APPLICABLE: colors.HexColor("#6B605A"),
}


def generate_pdf_report(
    output_path: str,
    report: ComplianceReport,
    product_name: str,
    inspector_email: str | None,
    image_path: str | None = None,
    font_size_tier: str = "tier1",
    image_quality_warning: str | None = None,
) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontSize=18)
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)

    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    story = []

    story.append(Paragraph("Legal Metrology Packaged Commodities — Compliance Report", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Product: {product_name}", body))
    story.append(Paragraph(f"Inspector: {inspector_email or 'N/A'}", body))
    story.append(Paragraph(f"Scan date: {dt.datetime.utcnow().isoformat(timespec='seconds')} UTC", body))
    story.append(Paragraph(f"Ruleset version: {report.ruleset_version}", body))
    story.append(Spacer(1, 10))

    overall_color = STATUS_COLORS[report.overall_status]
    summary_style = ParagraphStyle("Summary", parent=h2, textColor=overall_color)
    story.append(Paragraph(f"Overall status: {report.overall_status.value}", summary_style))
    score = report.compliance_score
    score_text = f"{score}% of applicable checks passed" if score is not None else "N/A"
    story.append(Paragraph(
        f"Summary (secondary metric — see itemized results below): {report.pass_count} PASS, "
        f"{report.fail_count} FAIL, {report.needs_verification_count} NEEDS VERIFICATION "
        f"({score_text}).", body,
    ))
    story.append(Spacer(1, 10))

    if image_quality_warning:
        warning_style = ParagraphStyle(
            # Mirrors --color-advisory-* in tokens.css: deliberately not any status color,
            # because a bad photo is an advisory, not a compliance verdict.
            "QualityWarning", parent=body, textColor=colors.HexColor("#5A4632"),
            backColor=colors.HexColor("#FBF0DA"), borderColor=colors.HexColor("#5E9DA3"),
            borderWidth=1, borderPadding=6,
        )
        story.append(Paragraph(f"<b>Possible bad photo, not a bad product:</b> {image_quality_warning}", warning_style))
        story.append(Spacer(1, 10))

    if image_path:
        try:
            story.append(Image(image_path, width=100 * mm, height=75 * mm))
            story.append(Spacer(1, 10))
        except Exception:
            pass

    story.append(Paragraph("Itemized rule-cited results", h2))
    table_data = [["Rule", "Requirement", "Status", "Evidence / Notes"]]
    for r in report.results:
        evidence_text = r.evidence.extracted_value or ""
        notes = r.notes or ""
        combined = (evidence_text + ("<br/>" if evidence_text and notes else "") + notes) or "—"
        table_data.append([
            Paragraph(f"{r.rule_id}<br/>{r.rule_reference}", small),
            Paragraph(r.requirement_text, small),
            Paragraph(r.status.value, ParagraphStyle("st", parent=small, textColor=STATUS_COLORS[r.status])),
            Paragraph(combined, small),
        ])
    table = Table(table_data, colWidths=[28 * mm, 55 * mm, 22 * mm, 65 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Methodology", h2))
    story.append(Paragraph(
        "Declarations were extracted via offline OCR (Tesseract, eng+hin+guj) followed by "
        "regex/keyword-anchored structured extraction. Any declaration read from a low-confidence "
        "OCR region is marked NEEDS VERIFICATION rather than an automated PASS. Font-size findings "
        f"in this report used <b>{'Tier 2 (calibrated, mm-accurate against Rule 7 tables)' if font_size_tier == 'tier2' else 'Tier 1 (relative comparison only — NOT a calibrated millimetre measurement; provide a reference dimension for a Tier 2 check)'}</b>. "
        "Items whose underlying legal threshold is marked 'VERIFY WITH DoCA' in "
        "docs/LEGAL_REQUIREMENTS.md are never auto PASS/FAIL — they return NEEDS VERIFICATION. "
        "R8-1 (declarations grouped on the principal display panel) is a 2D image-plane proximity "
        "proxy for \"same panel\", not a certified multi-panel/3D determination — a PASS/FAIL here "
        "is a signal, not a legal certification of panel placement. R8-2 (net-quantity clear "
        "space) checks Rule 8(1)'s proviso directly (no calibration needed, unlike Rule 7) but "
        "approximates numeral height from the OCR text line, which may overstate it. See "
        "LEGAL_REQUIREMENTS.md §10 for both. "
        "This report is a decision-support tool for enforcement officials, not a final legal "
        "determination.", small,
    ))

    doc.build(story)
