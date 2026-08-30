from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db import get_db
from app.models.orm import Scan

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{scan_id}/pdf")
def download_pdf(scan_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.pdf_report_path:
        raise HTTPException(404, "Report not found")
    return FileResponse(scan.pdf_report_path, media_type="application/pdf",
                         filename=f"compliance_report_{scan_id}.pdf")


@router.get("/{scan_id}/docx")
def download_docx(scan_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.docx_report_path:
        raise HTTPException(404, "Report not found")
    return FileResponse(
        scan.docx_report_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"compliance_report_{scan_id}.docx",
    )
