"""Isi data master contoh lewat ORM, sehingga jalan di SQLite maupun PostgreSQL.

    python -m scripts.seed_contoh

Aman dijalankan ulang: periode dengan kode yang sama tidak diduplikasi.
Preferensi sengaja tidak diisi di sini supaya bisa dicoba lewat endpoint API.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine, get_session_factory
from app.models import Dosen, KuotaDosen, Mahasiswa, Periode, PeriodeStatus

KODE_PERIODE = "2026-GANJIL"

DOSEN = [
    ("0001018501", "Dr. Andi Pratama", "andi.pratama@kampus.ac.id", "Rekayasa Perangkat Lunak", 2),
    ("0002028702", "Dr. Bella Kusuma", "bella.kusuma@kampus.ac.id", "Kecerdasan Artifisial", 1),
    ("0003039003", "Dr. Candra Wijaya", "candra.wijaya@kampus.ac.id", "Basis Data", 1),
]

MAHASISWA = [
    ("2210001", "Ahmad Fauzi", "ahmad.fauzi@kampus.ac.id"),
    ("2210002", "Bunga Lestari", "bunga.lestari@kampus.ac.id"),
    ("2210003", "Citra Dewi", "citra.dewi@kampus.ac.id"),
    ("2210004", "Dimas Saputra", "dimas.saputra@kampus.ac.id"),
    ("2210005", "Eka Wulandari", "eka.wulandari@kampus.ac.id"),
]


def seed(db: Session) -> Periode | None:
    existing = db.scalars(select(Periode).where(Periode.kode == KODE_PERIODE)).first()
    if existing is not None:
        return None

    sekarang = datetime.now(timezone.utc)
    periode = Periode(
        kode=KODE_PERIODE,
        nama="Periode Skripsi 2026 Ganjil",
        status=PeriodeStatus.OPEN,
        tanggal_mulai=date(2026, 9, 1),
        tanggal_selesai=date(2027, 1, 31),
        batas_preferensi=sekarang + timedelta(days=14),
        max_preferensi=3,
    )
    db.add(periode)
    db.flush()

    for nidn, nama, email, bidang, kuota in DOSEN:
        dosen = db.scalars(select(Dosen).where(Dosen.nidn == nidn)).first()
        if dosen is None:
            dosen = Dosen(nidn=nidn, nama=nama, email=email, bidang_keahlian=bidang)
            db.add(dosen)
            db.flush()
        sudah_ada = db.scalars(
            select(KuotaDosen).where(
                KuotaDosen.periode_id == periode.id, KuotaDosen.dosen_id == dosen.id
            )
        ).first()
        if sudah_ada is None:
            db.add(KuotaDosen(periode_id=periode.id, dosen_id=dosen.id, kuota=kuota))

    for nim, nama, email in MAHASISWA:
        if db.scalars(select(Mahasiswa).where(Mahasiswa.nim == nim)).first() is None:
            db.add(Mahasiswa(nim=nim, nama=nama, email=email, angkatan=2022))

    db.commit()
    return periode


if __name__ == "__main__":
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session_factory()() as session:
        hasil = seed(session)
        if hasil is None:
            print(f"Periode {KODE_PERIODE} sudah ada; tidak ada yang diubah.")
        else:
            print(f"Periode '{hasil.kode}' dibuat (id={hasil.id}, status={hasil.status.value}).")
            print(f"Dosen: {len(DOSEN)} | Mahasiswa: {len(MAHASISWA)} | Total kuota: {sum(d[4] for d in DOSEN)}")
            print("\nLangkah berikut di http://localhost:8000/docs :")
            print(f"  1. POST /api/preferensi        periode_id={hasil.id}, mahasiswa_id=1..5")
            print(f"  2. POST /api/preferensi/dosen  periode_id={hasil.id}, dosen_id=1..3")
            print(f"  3. POST /api/matching/execute  periode_id={hasil.id}, tahap=utama")
            print(f"  4. GET  /api/alokasi?periode_id={hasil.id}")