"""Akses DB terpusat. Service lain tidak menulis query SQLAlchemy secara langsung."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Alokasi,
    AlokasiStatus,
    Dosen,
    KuotaDosen,
    Mahasiswa,
    Periode,
    PreferensiDosen,
    PreferensiMahasiswa,
)
from app.services.exceptions import NotFoundError


def pastikan_utc(value: datetime) -> datetime:
    """SQLite mengembalikan datetime naive; PostgreSQL aware. Samakan sebelum dibanding."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def ambil_periode(db: Session, periode_id: int, *, untuk_dikunci: bool = False) -> Periode:
    stmt = select(Periode).where(Periode.id == periode_id)
    if untuk_dikunci:
        stmt = stmt.with_for_update()
    periode = db.scalars(stmt).one_or_none()
    if periode is None:
        raise NotFoundError(f"Periode {periode_id} tidak ditemukan")
    return periode


def ambil_mahasiswa(db: Session, mahasiswa_id: int) -> Mahasiswa:
    mahasiswa = db.get(Mahasiswa, mahasiswa_id)
    if mahasiswa is None:
        raise NotFoundError(f"Mahasiswa {mahasiswa_id} tidak ditemukan")
    return mahasiswa


def ambil_dosen(db: Session, dosen_id: int) -> Dosen:
    dosen = db.get(Dosen, dosen_id)
    if dosen is None:
        raise NotFoundError(f"Dosen {dosen_id} tidak ditemukan")
    return dosen


def ambil_kuota(db: Session, periode_id: int) -> dict[int, int]:
    rows = db.scalars(
        select(KuotaDosen).where(KuotaDosen.periode_id == periode_id).order_by(KuotaDosen.dosen_id)
    ).all()
    return {row.dosen_id: row.kuota for row in rows}


def ambil_preferensi_mahasiswa(
    db: Session, periode_id: int, mahasiswa_ids: list[int] | None = None
) -> dict[int, list[int]]:
    stmt = (
        select(PreferensiMahasiswa)
        .where(PreferensiMahasiswa.periode_id == periode_id)
        .order_by(PreferensiMahasiswa.mahasiswa_id, PreferensiMahasiswa.urutan)
    )
    if mahasiswa_ids is not None:
        stmt = stmt.where(PreferensiMahasiswa.mahasiswa_id.in_(mahasiswa_ids))
    hasil: dict[int, list[int]] = {}
    for row in db.scalars(stmt):
        hasil.setdefault(row.mahasiswa_id, []).append(row.dosen_id)
    return hasil


def ambil_preferensi_dosen(
    db: Session, periode_id: int, dosen_ids: list[int] | None = None
) -> dict[int, list[int]]:
    stmt = (
        select(PreferensiDosen)
        .where(PreferensiDosen.periode_id == periode_id)
        .order_by(PreferensiDosen.dosen_id, PreferensiDosen.urutan)
    )
    if dosen_ids is not None:
        stmt = stmt.where(PreferensiDosen.dosen_id.in_(dosen_ids))
    hasil: dict[int, list[int]] = {}
    for row in db.scalars(stmt):
        hasil.setdefault(row.dosen_id, []).append(row.mahasiswa_id)
    return hasil


def ambil_submit_pertama(db: Session, periode_id: int) -> dict[int, datetime]:
    rows = db.execute(
        select(
            PreferensiMahasiswa.mahasiswa_id,
            PreferensiMahasiswa.submit_pertama_pada,
        )
        .where(PreferensiMahasiswa.periode_id == periode_id)
        .distinct()
    ).all()
    return {mahasiswa_id: pastikan_utc(waktu) for mahasiswa_id, waktu in rows}


def ambil_alokasi(
    db: Session, periode_id: int, *, status: AlokasiStatus | None = None
) -> list[Alokasi]:
    stmt = select(Alokasi).where(Alokasi.periode_id == periode_id).order_by(Alokasi.mahasiswa_id)
    if status is not None:
        stmt = stmt.where(Alokasi.status == status)
    return list(db.scalars(stmt))