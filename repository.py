"""Persistence for estimates (thin wrapper around SQLAlchemy)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import EstimateRecord


class EstimateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: EstimateRecord) -> EstimateRecord:
        self.session.add(record)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        self.session.refresh(record)
        return record

    def get(self, estimate_id: str) -> EstimateRecord | None:
        return self.session.get(EstimateRecord, estimate_id)

    def list(self, limit: int, offset: int) -> tuple[list[EstimateRecord], int]:
        total = self.session.scalar(select(func.count()).select_from(EstimateRecord)) or 0
        rows = self.session.scalars(
            select(EstimateRecord)
            .order_by(EstimateRecord.created_at.desc(), EstimateRecord.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total
