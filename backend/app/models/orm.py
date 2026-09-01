from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="inspector")  # inspector | admin
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    scans: Mapped[list["Scan"]] = relationship(back_populates="product")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    inspector_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_path: Mapped[str] = mapped_column(String(1024))
    preprocessed_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    annotated_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_ocr_json: Mapped[str] = mapped_column(Text)
    declarations_json: Mapped[str] = mapped_column(Text)
    rule_results_json: Mapped[str] = mapped_column(Text)
    ruleset_version: Mapped[str] = mapped_column(String(64))
    overall_status: Mapped[str] = mapped_column(String(32))
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    font_size_tier: Mapped[str] = mapped_column(String(16), default="tier1")
    pdf_report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    docx_report_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)

    product: Mapped["Product | None"] = relationship(back_populates="scans")


class RuleVerification(Base):
    """Append-only audit trail of human overrides of a NEEDS_VERIFICATION rule result.

    The upgraded status is also materialised into Scan.rule_results_json so reads stay a single
    query, but THIS table is the record. A materialised status can be recomputed, overwritten by
    a later rescan, or edited; an inspection finding that a named official signed off on needs a
    row that is only ever inserted. Rows are never updated or deleted -- if a rule is verified
    again, that is another row, and the history stays legible.

    No unique constraint on (scan_id, rule_id) for the same reason: the constraint belongs in the
    endpoint, which refuses to verify anything that is not currently NEEDS_VERIFICATION, not in
    the audit log, whose job is to record what happened rather than to prevent it.
    """

    __tablename__ = "rule_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(32), index=True)
    # What the engine said before the override -- stored here as well as on the result JSON so the
    # audit row is self-contained and stays meaningful even if the scan is later re-run.
    original_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    verified_by: Mapped[str] = mapped_column(String(255), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc), index=True
    )
