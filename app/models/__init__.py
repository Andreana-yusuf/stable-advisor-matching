"""Impor seluruh model di satu tempat agar Base.metadata lengkap untuk create_all/DDL."""

from app.models.alokasi import Alokasi
from app.models.dosen import Dosen, KuotaDosen
from app.models.enums import AlokasiStatus, PeriodeStatus, Tahap
from app.models.mahasiswa import Mahasiswa
from app.models.periode import Periode
from app.models.preferensi import PreferensiDosen, PreferensiMahasiswa

__all__ = [
    "Alokasi",
    "AlokasiStatus",
    "Dosen",
    "KuotaDosen",
    "Mahasiswa",
    "Periode",
    "PeriodeStatus",
    "PreferensiDosen",
    "PreferensiMahasiswa",
    "Tahap",
]