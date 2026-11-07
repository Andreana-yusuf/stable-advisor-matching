from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import alokasi, matching, preferensi

api_router = APIRouter(prefix="/api")
api_router.include_router(preferensi.router)
api_router.include_router(matching.router)
api_router.include_router(alokasi.router)