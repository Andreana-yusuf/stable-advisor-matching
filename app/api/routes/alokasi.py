from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DBSession
from app.models import AlokasiStatus, Tahap
from app.schemas.alokasi import AlokasiListResponse
from app.services import alokasi_service

router = APIRouter(prefix="/alokasi", tags=["alokasi"])


@router.get("", response_model=AlokasiListResponse, summary="Lihat hasil alokasi")
def lihat_alokasi(
    db: DBSession,
    periode_id: Annotated[int, Query(gt=0)],
    mahasiswa_id: Annotated[int | None, Query(gt=0)] = None,
    dosen_id: Annotated[int | None, Query(gt=0)] = None,
    status: AlokasiStatus | None = None,
    tahap: Tahap | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AlokasiListResponse:
    return alokasi_service.daftar_alokasi(
        db,
        periode_id=periode_id,
        mahasiswa_id=mahasiswa_id,
        dosen_id=dosen_id,
        status=status,
        tahap=tahap,
        page=page,
        page_size=page_size,
    )