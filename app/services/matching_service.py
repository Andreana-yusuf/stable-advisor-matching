"""Orkestrasi: muat data -> panggil pure function -> verifikasi -> persist.

Seluruh keputusan alokasi dibuat oleh app.algorithms (tanpa I/O). Service ini
hanya menyiapkan input, menegakkan aturan periode, dan menyimpan hasil.
"""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.algorithms import (
    Assignment,
    MatchingResult,
    UnrankedPolicy,
    VerificationReport,
    gale_shapley,
    match_late_registrants,
    residual_capacity,
    verify_matching,
)
from app.models import Alokasi, AlokasiStatus, Periode, PeriodeStatus, Tahap
from app.schemas.matching import (
    AlokasiRingkasOutput,
    BlockingPairOutput,
    MatchingExecuteRequest,
    MatchingExecuteResponse,
    PelanggaranKuotaOutput,
    PelanggaranRasionalitasOutput,
    VerifikasiOutput,
)
from app.services import repository as repo
from app.services.exceptions import ConflictError, InputError, MatchingTidakStabilError

_STATUS_UTAMA = {PeriodeStatus.DRAFT, PeriodeStatus.OPEN, PeriodeStatus.TENTATIF}
_STATUS_SUSULAN = {PeriodeStatus.TENTATIF, PeriodeStatus.TERKUNCI, PeriodeStatus.SUSULAN}


def eksekusi_matching(db: Session, payload: MatchingExecuteRequest) -> MatchingExecuteResponse:
    # FOR UPDATE pada baris periode mencegah dua eksekusi admin berjalan bersamaan.
    periode = repo.ambil_periode(db, payload.periode_id, untuk_dikunci=True)
    kuota = repo.ambil_kuota(db, periode.id)
    if not kuota:
        raise ConflictError(f"Periode {periode.kode} belum memiliki kuota dosen")
    if sum(kuota.values()) == 0:
        raise ConflictError(f"Total kuota dosen pada periode {periode.kode} adalah nol")

    preferensi_dosen = repo.ambil_preferensi_dosen(db, periode.id)
    terkunci = {
        a.mahasiswa_id: a.dosen_id
        for a in repo.ambil_alokasi(db, periode.id, status=AlokasiStatus.TERKUNCI)
    }

    if payload.tahap is Tahap.UTAMA:
        hasil, laporan, jumlah_terkunci = _jalankan_utama(
            db, periode, payload, kuota, preferensi_dosen, terkunci
        )
        peserta_ids = list(hasil.student_to_lecturer) + list(hasil.unmatched)
    else:
        hasil, laporan, jumlah_terkunci, peserta_ids = _jalankan_susulan(
            db, periode, payload, kuota, preferensi_dosen, terkunci
        )

    if not laporan.is_stable:
        raise MatchingTidakStabilError(
            "Hasil algoritma gagal verifikasi kestabilan; tidak ada data yang disimpan",
            detail=_verifikasi_output(laporan).model_dump(),
        )

    tersimpan = False
    if not payload.dry_run:
        _persist(db, periode, payload, hasil, peserta_ids)
        tersimpan = True

    baru = hasil.newly_assigned
    return MatchingExecuteResponse(
        periode_id=periode.id,
        tahap=payload.tahap,
        dry_run=payload.dry_run,
        tersimpan=tersimpan,
        jumlah_peserta=len(peserta_ids),
        jumlah_alokasi_baru=len(baru),
        jumlah_alokasi_terkunci_dipertahankan=jumlah_terkunci,
        mahasiswa_tidak_teralokasi=[int(s) for s in hasil.unmatched],
        jumlah_ronde=hasil.rounds,
        jumlah_proposal=hasil.proposal_count,
        verifikasi=_verifikasi_output(laporan),
        alokasi_baru=[_alokasi_ringkas(a, payload.kunci) for a in baru],
    )


def _jalankan_utama(
    db: Session,
    periode: Periode,
    payload: MatchingExecuteRequest,
    kuota: dict[int, int],
    preferensi_dosen: dict[int, list[int]],
    terkunci: dict[int, int],
) -> tuple[MatchingResult, VerificationReport, int]:
    if terkunci:
        raise ConflictError(
            "Sudah ada alokasi terkunci pada periode ini; gunakan tahap susulan untuk menambah alokasi"
        )
    if periode.status not in _STATUS_UTAMA:
        raise ConflictError(
            f"Tahap utama tidak dapat dijalankan saat periode berstatus {periode.status.value}"
        )
    preferensi_mahasiswa = repo.ambil_preferensi_mahasiswa(db, periode.id)
    if not preferensi_mahasiswa:
        raise ConflictError("Belum ada mahasiswa yang mengisi preferensi pada periode ini")

    kebijakan = payload.kebijakan_tak_terperingkat or UnrankedPolicy.REJECT
    urutan = tuple(preferensi_mahasiswa)
    hasil = gale_shapley(
        preferensi_mahasiswa,
        preferensi_dosen,
        kuota,
        kebijakan_tak_terperingkat=kebijakan,
        urutan_pengusul=urutan,
    )
    laporan = verify_matching(
        hasil.student_to_lecturer,
        preferensi_mahasiswa,
        preferensi_dosen,
        kuota,
        kebijakan_tak_terperingkat=kebijakan,
        urutan_pengusul=urutan,
    )
    return hasil, laporan, 0


def _jalankan_susulan(
    db: Session,
    periode: Periode,
    payload: MatchingExecuteRequest,
    kuota: dict[int, int],
    preferensi_dosen: dict[int, list[int]],
    terkunci: dict[int, int],
) -> tuple[MatchingResult, VerificationReport, int, list[int]]:
    if periode.status not in _STATUS_SUSULAN:
        raise ConflictError(
            f"Tahap susulan memerlukan periode berstatus tentatif/terkunci/susulan, "
            f"saat ini {periode.status.value}"
        )
    peserta_ids = _tentukan_peserta_susulan(db, periode.id, payload.mahasiswa_ids, terkunci)
    preferensi_mahasiswa = repo.ambil_preferensi_mahasiswa(db, periode.id, peserta_ids)
    submit_pertama = repo.ambil_submit_pertama(db, periode.id)
    # Late-register diproses sesuai urutan kedatangan agar reproducible dan adil.
    urutan = tuple(sorted(preferensi_mahasiswa, key=lambda m: (submit_pertama.get(m), m)))

    kebijakan = payload.kebijakan_tak_terperingkat or UnrankedPolicy.APPEND
    kapasitas_sisa = residual_capacity(kuota, terkunci)
    hasil = match_late_registrants(
        preferensi_mahasiswa,
        preferensi_dosen,
        kuota,
        terkunci,
        kebijakan_tak_terperingkat=kebijakan,
        urutan_pengusul=urutan,
    )
    if hasil.locked != terkunci:
        raise MatchingTidakStabilError("Alokasi terkunci berubah saat mekanisme susulan")

    baru = {a.student_id: a.lecturer_id for a in hasil.newly_assigned}
    # Kestabilan diuji pada pasar residual: kursi terkunci sudah dikeluarkan dari kuota.
    laporan = verify_matching(
        baru,
        preferensi_mahasiswa,
        preferensi_dosen,
        kapasitas_sisa,
        kebijakan_tak_terperingkat=kebijakan,
        urutan_pengusul=urutan,
    )
    return hasil, laporan, len(terkunci), peserta_ids


def _tentukan_peserta_susulan(
    db: Session, periode_id: int, diminta: list[int] | None, terkunci: dict[int, int]
) -> list[int]:
    pengisi_preferensi = repo.ambil_preferensi_mahasiswa(db, periode_id)
    if diminta is not None:
        if not diminta:
            raise InputError("mahasiswa_ids tidak boleh kosong; kirim null untuk memilih otomatis")
        if len(set(diminta)) != len(diminta):
            raise InputError("mahasiswa_ids memuat duplikat")
        for mahasiswa_id in diminta:
            if mahasiswa_id in terkunci:
                raise ConflictError(f"Mahasiswa {mahasiswa_id} sudah memiliki alokasi terkunci")
            if mahasiswa_id not in pengisi_preferensi:
                raise InputError(f"Mahasiswa {mahasiswa_id} belum mengisi preferensi")
        return list(diminta)

    otomatis = [m for m in pengisi_preferensi if m not in terkunci]
    if not otomatis:
        raise ConflictError("Tidak ada mahasiswa yang perlu diproses pada tahap susulan")
    return otomatis


def _persist(
    db: Session,
    periode: Periode,
    payload: MatchingExecuteRequest,
    hasil: MatchingResult,
    peserta_ids: list[int],
) -> None:
    status_baru = AlokasiStatus.TERKUNCI if payload.kunci else AlokasiStatus.TENTATIF
    hapus = delete(Alokasi).where(
        Alokasi.periode_id == periode.id, Alokasi.status == AlokasiStatus.TENTATIF
    )
    if payload.tahap is Tahap.SUSULAN:
        hapus = hapus.where(Alokasi.mahasiswa_id.in_(peserta_ids))
    db.execute(hapus)
    db.add_all(
        Alokasi(
            periode_id=periode.id,
            mahasiswa_id=int(a.student_id),
            dosen_id=int(a.lecturer_id),
            tahap=payload.tahap,
            status=status_baru,
            peringkat_mahasiswa=a.student_rank,
            peringkat_dosen=a.lecturer_rank,
            ronde=a.round_number,
        )
        for a in hasil.newly_assigned
    )
    if payload.tahap is Tahap.UTAMA:
        periode.status = PeriodeStatus.TERKUNCI if payload.kunci else PeriodeStatus.TENTATIF
    else:
        periode.status = PeriodeStatus.TERKUNCI if payload.kunci else PeriodeStatus.SUSULAN
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Hasil alokasi melanggar constraint database (kuota/keunikan); perubahan dibatalkan",
            detail=str(exc.orig),
        ) from exc


def _verifikasi_output(laporan: VerificationReport) -> VerifikasiOutput:
    return VerifikasiOutput(
        stabil=laporan.is_stable,
        jumlah_blocking_pair=len(laporan.blocking_pairs),
        blocking_pairs=[
            BlockingPairOutput(
                mahasiswa_id=int(b.student_id),
                dosen_id=int(b.lecturer_id),
                peringkat_mahasiswa=b.student_rank,
                peringkat_dosen=b.lecturer_rank,
                alasan=b.reason,
                mahasiswa_tergusur_id=(
                    int(b.displaced_student_id) if b.displaced_student_id is not None else None
                ),
            )
            for b in laporan.blocking_pairs
        ],
        pelanggaran_kuota=[
            PelanggaranKuotaOutput(dosen_id=int(v.lecturer_id), terisi=v.assigned, kuota=v.quota)
            for v in laporan.quota_violations
        ],
        pelanggaran_rasionalitas=[
            PelanggaranRasionalitasOutput(
                mahasiswa_id=int(v.student_id), dosen_id=int(v.lecturer_id), alasan=v.reason
            )
            for v in laporan.rationality_violations
        ],
    )


def _alokasi_ringkas(a: Assignment, kunci: bool) -> AlokasiRingkasOutput:
    return AlokasiRingkasOutput(
        mahasiswa_id=int(a.student_id),
        dosen_id=int(a.lecturer_id),
        peringkat_mahasiswa=a.student_rank,
        peringkat_dosen=a.lecturer_rank,
        ronde=a.round_number,
        terkunci=kunci and not a.is_locked,
    )