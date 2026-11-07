"""Validasi dan penyimpanan preferensi kedua sisi pasar."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Alokasi,
    AlokasiStatus,
    Dosen,
    KuotaDosen,
    PeriodeStatus,
    PreferensiDosen,
    PreferensiMahasiswa,
)
from app.schemas.preferensi import (
    PreferensiDosenInput,
    PreferensiDosenOutput,
    PreferensiMahasiswaInput,
    PreferensiMahasiswaOutput,
)
from app.services import repository as repo
from app.services.exceptions import ConflictError, InputError, NotFoundError

_STATUS_BOLEH_INPUT = {
    PeriodeStatus.DRAFT,
    PeriodeStatus.OPEN,
    PeriodeStatus.TENTATIF,
    PeriodeStatus.TERKUNCI,
    PeriodeStatus.SUSULAN,
}


def simpan_preferensi_mahasiswa(
    db: Session, payload: PreferensiMahasiswaInput
) -> PreferensiMahasiswaOutput:
    periode = repo.ambil_periode(db, payload.periode_id)
    if periode.status not in _STATUS_BOLEH_INPUT:
        raise ConflictError(f"Periode berstatus {periode.status.value} tidak menerima preferensi")

    mahasiswa = repo.ambil_mahasiswa(db, payload.mahasiswa_id)
    if not mahasiswa.is_active:
        raise ConflictError(f"Mahasiswa {mahasiswa.nim} tidak aktif")

    terkunci = db.scalars(
        select(Alokasi.id).where(
            Alokasi.periode_id == periode.id,
            Alokasi.mahasiswa_id == mahasiswa.id,
            Alokasi.status == AlokasiStatus.TERKUNCI,
        )
    ).first()
    if terkunci is not None:
        raise ConflictError("Preferensi tidak dapat diubah karena alokasi sudah terkunci")

    if len(payload.dosen_ids) > periode.max_preferensi:
        raise InputError(
            f"Jumlah preferensi melebihi batas periode ({periode.max_preferensi}): "
            f"{len(payload.dosen_ids)}"
        )

    _validasi_dosen_terpilih(db, periode.id, payload.dosen_ids)

    waktu_submit = repo.ambil_submit_pertama(db, periode.id).get(
        mahasiswa.id, datetime.now(timezone.utc)
    )
    db.execute(
        delete(PreferensiMahasiswa).where(
            PreferensiMahasiswa.periode_id == periode.id,
            PreferensiMahasiswa.mahasiswa_id == mahasiswa.id,
        )
    )
    db.add_all(
        PreferensiMahasiswa(
            periode_id=periode.id,
            mahasiswa_id=mahasiswa.id,
            dosen_id=dosen_id,
            urutan=urutan,
            submit_pertama_pada=waktu_submit,
        )
        for urutan, dosen_id in enumerate(payload.dosen_ids, start=1)
    )
    db.commit()
    return PreferensiMahasiswaOutput(
        periode_id=periode.id,
        mahasiswa_id=mahasiswa.id,
        dosen_ids=payload.dosen_ids,
        jumlah=len(payload.dosen_ids),
        late_register=waktu_submit > repo.pastikan_utc(periode.batas_preferensi),
    )


def simpan_preferensi_dosen(db: Session, payload: PreferensiDosenInput) -> PreferensiDosenOutput:
    periode = repo.ambil_periode(db, payload.periode_id)
    if periode.status is PeriodeStatus.SELESAI:
        raise ConflictError("Periode sudah selesai, preferensi dosen tidak dapat diubah")

    dosen = repo.ambil_dosen(db, payload.dosen_id)
    if not dosen.is_active:
        raise ConflictError(f"Dosen {dosen.nidn} tidak aktif")

    kuota = db.scalars(
        select(KuotaDosen.kuota).where(
            KuotaDosen.periode_id == periode.id, KuotaDosen.dosen_id == dosen.id
        )
    ).first()
    if kuota is None:
        raise InputError(f"Dosen {dosen.nidn} belum memiliki kuota pada periode {periode.kode}")

    # Mengubah peringkat dosen setelah alokasi dikunci akan membatalkan jaminan
    # kestabilan pasangan yang sudah terkunci, jadi ditutup.
    ada_terkunci = db.scalars(
        select(Alokasi.id).where(
            Alokasi.periode_id == periode.id, Alokasi.status == AlokasiStatus.TERKUNCI
        )
    ).first()
    if ada_terkunci is not None:
        raise ConflictError(
            "Preferensi dosen tidak dapat diubah setelah ada alokasi terkunci pada periode ini"
        )

    _validasi_mahasiswa_terpilih(db, payload.mahasiswa_ids)

    db.execute(
        delete(PreferensiDosen).where(
            PreferensiDosen.periode_id == periode.id, PreferensiDosen.dosen_id == dosen.id
        )
    )
    db.add_all(
        PreferensiDosen(
            periode_id=periode.id,
            dosen_id=dosen.id,
            mahasiswa_id=mahasiswa_id,
            urutan=urutan,
        )
        for urutan, mahasiswa_id in enumerate(payload.mahasiswa_ids, start=1)
    )
    db.commit()
    return PreferensiDosenOutput(
        periode_id=periode.id,
        dosen_id=dosen.id,
        mahasiswa_ids=payload.mahasiswa_ids,
        jumlah=len(payload.mahasiswa_ids),
    )


def _validasi_dosen_terpilih(db: Session, periode_id: int, dosen_ids: list[int]) -> None:
    kuota = repo.ambil_kuota(db, periode_id)
    for dosen_id in dosen_ids:
        if dosen_id not in kuota:
            raise InputError(f"Dosen {dosen_id} belum memiliki kuota pada periode {periode_id}")
        dosen = db.get(Dosen, dosen_id)
        if dosen is None:
            raise NotFoundError(f"Dosen {dosen_id} tidak ditemukan")
        if not dosen.is_active:
            raise ConflictError(f"Dosen {dosen.nidn} tidak aktif")


def _validasi_mahasiswa_terpilih(db: Session, mahasiswa_ids: list[int]) -> None:
    for mahasiswa_id in mahasiswa_ids:
        mahasiswa = repo.ambil_mahasiswa(db, mahasiswa_id)
        if not mahasiswa.is_active:
            raise ConflictError(f"Mahasiswa {mahasiswa.nim} tidak aktif")