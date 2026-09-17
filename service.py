"""Application service: parse -> calculate -> persist -> present."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import timezone

from sqlalchemy.orm import Session

from app.calculator import calculate
from app.db import EstimateRecord
from app.parser import parse_request
from app.repository import EstimateRepository
from app.schemas import EstimateOut

logger = logging.getLogger(__name__)


class UnparseableRequestError(Exception):
    """The request contained nothing that could be priced."""

    def __init__(self, warnings: list[str]) -> None:
        super().__init__("No priceable materials or labor were found in the request.")
        self.warnings = warnings


class EstimateNotFoundError(Exception):
    pass


def _to_out(record: EstimateRecord) -> EstimateOut:
    created_at = record.created_at
    if created_at.tzinfo is None:  # SQLite drops tz info; values are stored in UTC
        created_at = created_at.replace(tzinfo=timezone.utc)
    return EstimateOut.model_validate(
        {
            **record.structured_output,
            "id": record.id,
            "created_at": created_at,
            "raw_input": record.raw_input,
        }
    )


class EstimateService:
    def __init__(self, session: Session) -> None:
        self.repo = EstimateRepository(session)

    def create(self, raw_text: str) -> EstimateOut:
        parsed = parse_request(raw_text)
        if parsed.is_empty:
            raise UnparseableRequestError(parsed.warnings)

        breakdown = calculate(parsed.materials, parsed.labor, parsed.complexity)
        structured = {
            "set_name": parsed.set_name,
            "complexity": parsed.complexity,
            "complexity_detected": parsed.complexity_detected,
            "materials": [asdict(line) for line in breakdown.materials],
            "labor": [asdict(line) for line in breakdown.labor],
            "material_cost_by_category": breakdown.material_cost_by_category,
            "labor_cost_by_role": breakdown.labor_cost_by_role,
            "summary": asdict(breakdown.summary),
            "warnings": parsed.warnings,
        }
        # Round-trip through the schema so the stored JSON is exactly the API shape.
        stored = EstimateOut.model_validate(
            {**structured, "id": "pending", "created_at": "1970-01-01T00:00:00Z", "raw_input": raw_text}
        ).model_dump(mode="json", exclude={"id", "created_at", "raw_input"})

        record = self.repo.add(
            EstimateRecord(
                raw_input=raw_text,
                set_name=parsed.set_name,
                complexity=parsed.complexity,
                material_cost=breakdown.summary.material_cost,
                labor_cost=breakdown.summary.labor_cost,
                total=breakdown.summary.total,
                structured_output=stored,
            )
        )
        logger.info("estimate created id=%s total=%s", record.id, record.total)
        return _to_out(record)

    def get(self, estimate_id: str) -> EstimateOut:
        record = self.repo.get(estimate_id)
        if record is None:
            raise EstimateNotFoundError(estimate_id)
        return _to_out(record)

    def list(self, limit: int, offset: int) -> tuple[list[EstimateOut], int]:
        records, total = self.repo.list(limit=limit, offset=offset)
        return [_to_out(r) for r in records], total
