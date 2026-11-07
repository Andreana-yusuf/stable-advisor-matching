from __future__ import annotations

from pydantic import BaseModel, Field

from app.algorithms.types import UnrankedPolicy
from app.models.enums import Tahap


class MatchingExecuteRequest(BaseModel):
    periode_id: int = Field(gt=0)
    tahap: Tahap = Tahap.UTAMA
    mahasiswa_ids: list[int] | None = Field(
        default=None,
        description="Khusus susulan: peserta yang diproses. Bila kosong, dipilih otomatis.",
    )
    kebijakan_tak_terperingkat: UnrankedPolicy | None = Field(
        default=None,
        description="Default: reject untuk utama, append untuk susulan.",
    )
    kunci: bool = Field(default=True, description="False = simpan sebagai tentatif untuk ditinjau")
    dry_run: bool = Field(default=False, description="Hitung dan verifikasi tanpa menyimpan")


class BlockingPairOutput(BaseModel):
    mahasiswa_id: int
    dosen_id: int
    peringkat_mahasiswa: int
    peringkat_dosen: int
    alasan: str
    mahasiswa_tergusur_id: int | None = None


class PelanggaranKuotaOutput(BaseModel):
    dosen_id: int
    terisi: int
    kuota: int


class PelanggaranRasionalitasOutput(BaseModel):
    mahasiswa_id: int
    dosen_id: int
    alasan: str


class VerifikasiOutput(BaseModel):
    stabil: bool
    jumlah_blocking_pair: int
    blocking_pairs: list[BlockingPairOutput]
    pelanggaran_kuota: list[PelanggaranKuotaOutput]
    pelanggaran_rasionalitas: list[PelanggaranRasionalitasOutput]


class AlokasiRingkasOutput(BaseModel):
    mahasiswa_id: int
    dosen_id: int
    peringkat_mahasiswa: int | None
    peringkat_dosen: int | None
    ronde: int
    terkunci: bool


class MatchingExecuteResponse(BaseModel):
    periode_id: int
    tahap: Tahap
    dry_run: bool
    tersimpan: bool
    jumlah_peserta: int
    jumlah_alokasi_baru: int
    jumlah_alokasi_terkunci_dipertahankan: int
    mahasiswa_tidak_teralokasi: list[int]
    jumlah_ronde: int
    jumlah_proposal: int
    verifikasi: VerifikasiOutput
    alokasi_baru: list[AlokasiRingkasOutput]