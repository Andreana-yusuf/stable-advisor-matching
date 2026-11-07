from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, DBSession
from app.schemas.matching import MatchingExecuteRequest, MatchingExecuteResponse
from app.services import matching_service

router = APIRouter(prefix="/matching", tags=["matching"])


@router.post(
    "/execute",
    response_model=MatchingExecuteResponse,
    summary="Eksekusi Gale-Shapley (admin)",
)
def eksekusi_matching(
    payload: MatchingExecuteRequest, db: DBSession, _: AdminUser
) -> MatchingExecuteResponse:
    """Tahap `utama` untuk seluruh pengisi preferensi, `susulan` untuk late-register.

    Hasil diverifikasi (blocking pair + kuota) sebelum dipersist; bila gagal,
    transaksi dibatalkan dan tidak ada alokasi yang tersimpan.
    """
    return matching_service.eksekusi_matching(db, payload)