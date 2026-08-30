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
