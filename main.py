"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.db import build_engine, build_session_factory, init_db
from app.service import EstimateNotFoundError, UnparseableRequestError

logger = logging.getLogger("set_estimator")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(engine)
        logger.info("database ready (%s)", engine.url.render_as_string(hide_password=True))
        yield
        engine.dispose()

    app = FastAPI(
        title="Set Construction Estimator",
        version="1.0.0",
        description="Turns plain-English set construction requests into rule-based cost estimates.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = build_session_factory(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(UnparseableRequestError)
    async def _unparseable(_: Request, exc: UnparseableRequestError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": {"message": str(exc), "warnings": exc.warnings}},
        )

    @app.exception_handler(EstimateNotFoundError)
    async def _not_found(_: Request, exc: EstimateNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": f"Estimate {exc} not found."})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    app.include_router(router)
    return app


app = create_app()
