from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import require_role
from app.db import get_db
from app.models.orm import Scan

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: dict = Depends(require_role("admin"))):
    total = db.query(func.count(Scan.id)).scalar() or 0
    by_status = dict(
        db.query(Scan.overall_status, func.count(Scan.id)).group_by(Scan.overall_status).all()
    )
    since = dt.datetime.utcnow() - dt.timedelta(days=30)
    trend_rows = (
        db.query(func.date(Scan.created_at), func.count(Scan.id))
        .filter(Scan.created_at >= since)
        .group_by(func.date(Scan.created_at))
        .order_by(func.date(Scan.created_at))
        .all()
    )
    recent_noncompliant = (
        db.query(Scan)
        .filter(Scan.overall_status == "FAIL")
        .order_by(Scan.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "total_scans": total,
        "by_status": by_status,
        "trend_30d": [{"date": str(d), "count": c} for d, c in trend_rows],
        "recent_noncompliant": [
            {
                "id": s.id,
                "product_name": s.product.name if s.product else "Unknown",
                "created_at": s.created_at.isoformat(),
                "compliance_score": s.compliance_score,
            }
            for s in recent_noncompliant
        ],
    }
