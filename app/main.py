from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.services.exceptions import DomainError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    if settings.admin_api_key == "dev-admin-key":
        logger.warning(
            "APP_ADMIN_API_KEY masih memakai nilai default development; ganti sebelum produksi."
        )
    aplikasi = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "MVP alokasi pembimbing skripsi dengan Gale-Shapley Student-Proposing "
            "(Deferred Acceptance). Hasil dijamin stabil dan patuh kuota."
        ),
        debug=settings.debug,
    )
    aplikasi.include_router(api_router)

    if settings.cors_origins:
        aplikasi.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    @aplikasi.exception_handler(DomainError)
    async def tangani_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        isi: dict[str, object] = {"detail": exc.pesan, "kode": exc.kode}
        if exc.detail is not None:
            isi["data"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=isi)

    @aplikasi.get("/health", tags=["infra"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return aplikasi


app = create_app()