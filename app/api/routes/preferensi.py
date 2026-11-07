from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DBSession
from app.schemas.preferensi import (
    PreferensiDosenInput,
    PreferensiDosenOutput,
    PreferensiMahasiswaInput,
    PreferensiMahasiswaOutput,
)
from app.services import preferensi_service

router = APIRouter(prefix="/preferensi", tags=["preferensi"])


@router.post(
    "",
    response_model=PreferensiMahasiswaOutput,
    status_code=201,
    summary="Simpan/revisi daftar preferensi dosen oleh mahasiswa",
)
def input_preferensi_mahasiswa(payload: PreferensiMahasiswaInput, db: DBSession) -> PreferensiMahasiswaOutput:
    """Daftar bersifat replace-all: urutan array menentukan peringkat (index 0 = pilihan 1)."""
    return preferensi_service.simpan_preferensi_mahasiswa(db, payload)


@router.post(
    "/dosen",
    response_model=PreferensiDosenOutput,
    status_code=201,
    summary="Simpan/revisi peringkat mahasiswa oleh dosen",
)
def input_preferensi_dosen(payload: PreferensiDosenInput, db: DBSession) -> PreferensiDosenOutput:
    return preferensi_service.simpan_preferensi_dosen(db, payload)