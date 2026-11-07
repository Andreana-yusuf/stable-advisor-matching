from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import AlokasiStatus, Tahap


class AlokasiOutput(BaseModel):
    id: int
    periode_id: int
    mahasiswa_id: int
    nim: str
    nama_mahasiswa: str
    dosen_id: int
    nidn: str
    nama_dosen: str
    tahap: Tahap
    status: AlokasiStatus
    peringkat_mahasiswa: int | None
    peringkat_dosen: int | None
    ronde: int
    dibuat_pada: datetime


class AlokasiListResponse(BaseModel):
    data: list[AlokasiOutput]
    total: int
    page: int
    page_size: int