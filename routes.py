"""HTTP routes."""

from __future__ import annotations

from typing import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.catalog import BULK_DISCOUNT, COMPLEXITY_SURCHARGE, LABOR, MATERIALS
from app.schemas import SAMPLE_REQUEST, EstimateListOut, EstimateOut, EstimateRequest, ErrorOut
from app.service import EstimateService

router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_service(session: Session = Depends(get_session)) -> EstimateService:
    return EstimateService(session)


async def read_request_text(request: Request) -> str:
    """Accept either ``{"text": "..."}`` JSON or a raw ``text/plain`` body."""
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    body = await request.body()
    max_chars = request.app.state.settings.max_input_chars

    if content_type == "application/json":
        try:
            payload = EstimateRequest.model_validate_json(body)
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(include_url=False, include_context=False, include_input=False),
            ) from exc
        text = payload.text
    elif content_type in ("text/plain", ""):
        try:
            raw = body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Body must be UTF-8 text.") from exc
        try:
            text = EstimateRequest(text=raw).text
        except ValidationError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(include_url=False, include_context=False, include_input=False),
            ) from exc
    else:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Send application/json ({\"text\": \"...\"}) or text/plain.",
        )

    if len(text) > max_chars:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Request exceeds {max_chars} characters.")
    return text


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/catalog", tags=["meta"], summary="Pricing rules used by the estimator")
def catalog() -> dict:
    return {
        "materials": MATERIALS,
        "labor": LABOR,
        "complexity_surcharge": COMPLEXITY_SURCHARGE,
        "bulk_discount": BULK_DISCOUNT,
    }


@router.post(
    "/estimates",
    response_model=EstimateOut,
    status_code=status.HTTP_201_CREATED,
    tags=["estimates"],
    summary="Create an estimate from a plain-English request",
    responses={422: {"model": ErrorOut}, 415: {"model": ErrorOut}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": EstimateRequest.model_json_schema()},
                "text/plain": {"schema": {"type": "string"}, "example": SAMPLE_REQUEST},
            },
        }
    },
)
async def create_estimate(request: Request, service: EstimateService = Depends(get_service)) -> EstimateOut:
    text = await read_request_text(request)
    return await run_in_threadpool(service.create, text)


@router.get("/estimates", response_model=EstimateListOut, tags=["estimates"], summary="List estimates, newest first")
def list_estimates(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: EstimateService = Depends(get_service),
) -> EstimateListOut:
    items, total = service.list(limit=limit, offset=offset)
    return EstimateListOut(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/estimates/{estimate_id}",
    response_model=EstimateOut,
    tags=["estimates"],
    summary="Get one estimate",
    responses={404: {"model": ErrorOut}},
)
def get_estimate(estimate_id: UUID, service: EstimateService = Depends(get_service)) -> EstimateOut:
    return service.get(str(estimate_id))
