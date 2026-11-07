"""Gale-Shapley Student-Proposing / Deferred Acceptance (many-to-one dengan kuota).

Fungsi di modul ini murni: tanpa I/O, tanpa DB, tanpa state global. Hasilnya
student-optimal di antara seluruh matching stabil untuk pasar yang diumpankan.
"""

from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence

from app.algorithms.preferences import (
    acceptable_choices,
    build_rank_map,
    extend_ranks,
    residual_capacity,
    validate_quotas,
)
from app.algorithms.types import (
    Assignment,
    LecturerId,
    MatchingResult,
    Rejection,
    RejectionReason,
    StudentId,
    UnrankedPolicy,
)

__all__ = ["gale_shapley", "match_late_registrants", "residual_capacity"]


def gale_shapley(
    preferensi_mahasiswa: Mapping[StudentId, Sequence[LecturerId]],
    preferensi_dosen: Mapping[LecturerId, Sequence[StudentId]],
    kuota_dosen: Mapping[LecturerId, int],
    *,
    kebijakan_tak_terperingkat: UnrankedPolicy = UnrankedPolicy.REJECT,
    urutan_pengusul: Sequence[StudentId] | None = None,
) -> MatchingResult:
    """Alokasi stabil student-optimal untuk satu putaran penuh (tahap utama).

    Mahasiswa mengusul berurutan sesuai daftar preferensinya; dosen menahan
    proposal terbaik sampai kuota penuh dan baru melepaskannya saat ada
    pelamar yang lebih baik. Karena itu tidak ada blocking pair di hasil akhir.
    """
    validate_quotas(kuota_dosen)
    student_ranks = build_rank_map(preferensi_mahasiswa, side="mahasiswa")
    lecturer_ranks = build_rank_map(preferensi_dosen, side="dosen")
    choices = acceptable_choices(preferensi_mahasiswa, kuota_dosen)
    order = tuple(urutan_pengusul) if urutan_pengusul is not None else tuple(choices)
    _validate_order(order, choices)
    extended = extend_ranks(lecturer_ranks, kuota_dosen, order, kebijakan_tak_terperingkat)
    return _deferred_acceptance(
        choices=choices,
        student_ranks=student_ranks,
        lecturer_ranks=extended,
        lecturer_ranks_asli=lecturer_ranks,
        capacity=dict(kuota_dosen),
        locked={},
        order=order,
    )


def match_late_registrants(
    preferensi_mahasiswa_susulan: Mapping[StudentId, Sequence[LecturerId]],
    preferensi_dosen: Mapping[LecturerId, Sequence[StudentId]],
    kuota_dosen: Mapping[LecturerId, int],
    alokasi_terkunci: Mapping[StudentId, LecturerId],
    *,
    kebijakan_tak_terperingkat: UnrankedPolicy = UnrankedPolicy.APPEND,
    urutan_pengusul: Sequence[StudentId] | None = None,
) -> MatchingResult:
    """Mekanisme susulan: mahasiswa late-register berebut sisa kuota saja.

    Alokasi terkunci diperlakukan sebagai kursi yang sudah terisi permanen:
    ia mengurangi kapasitas, tidak pernah digusur, dan tidak ikut mengusul.
    Hasilnya memuat alokasi terkunci (is_locked=True) sekaligus alokasi baru,
    sehingga caller bisa memverifikasi pasar gabungan lalu menyimpan yang baru.

    Kestabilan dijamin pada pasar residual. Pasangan terkunci sengaja dibekukan
    secara administratif, sehingga blocking pair yang melibatkan mahasiswa
    terkunci tidak dihitung sebagai pelanggaran (lihat find_blocking_pairs).
    """
    student_ranks = build_rank_map(preferensi_mahasiswa_susulan, side="mahasiswa")
    lecturer_ranks = build_rank_map(preferensi_dosen, side="dosen")
    capacity = residual_capacity(kuota_dosen, alokasi_terkunci)

    overlap = set(alokasi_terkunci) & set(preferensi_mahasiswa_susulan)
    if overlap:
        raise ValueError(f"Mahasiswa sudah terkunci tidak boleh ikut susulan: {sorted(overlap, key=str)!r}")

    choices = acceptable_choices(preferensi_mahasiswa_susulan, capacity)
    order = tuple(urutan_pengusul) if urutan_pengusul is not None else tuple(choices)
    _validate_order(order, choices)
    extended = extend_ranks(lecturer_ranks, capacity, order, kebijakan_tak_terperingkat)
    return _deferred_acceptance(
        choices=choices,
        student_ranks=student_ranks,
        lecturer_ranks=extended,
        lecturer_ranks_asli=lecturer_ranks,
        capacity=capacity,
        locked=dict(alokasi_terkunci),
        order=order,
    )


def _validate_order(order: Sequence[StudentId], choices: Mapping[StudentId, object]) -> None:
    if len(set(order)) != len(order):
        raise ValueError("urutan_pengusul memuat mahasiswa duplikat")
    unknown = [student for student in order if student not in choices]
    if unknown:
        raise ValueError(f"urutan_pengusul memuat mahasiswa tanpa preferensi: {unknown!r}")
    missing = [student for student in choices if student not in set(order)]
    if missing:
        raise ValueError(f"urutan_pengusul tidak memuat seluruh pengusul: {missing!r}")


def _deferred_acceptance(
    *,
    choices: Mapping[StudentId, Sequence[LecturerId]],
    student_ranks: Mapping[StudentId, Mapping[LecturerId, int]],
    lecturer_ranks: Mapping[LecturerId, Mapping[StudentId, int]],
    lecturer_ranks_asli: Mapping[LecturerId, Mapping[StudentId, int]],
    capacity: Mapping[LecturerId, int],
    locked: Mapping[StudentId, LecturerId],
    order: Sequence[StudentId],
) -> MatchingResult:
    order_index = {student: index for index, student in enumerate(order)}
    cursor = {student: 0 for student in order}
    # Kunci tuple (peringkat, indeks pengusul) memberi perbandingan total walau peringkat sama.
    held: dict[LecturerId, list[tuple[tuple[int, int], StudentId]]] = {
        lecturer: [] for lecturer in capacity
    }
    accepted_round: dict[StudentId, int] = {}
    queue: deque[StudentId] = deque(order)
    rejections: list[Rejection] = []
    rounds = 0
    proposals = 0

    while queue:
        rounds += 1
        wave = list(queue)
        queue.clear()
        for student in wave:
            options = choices[student]
            while cursor[student] < len(options):
                lecturer = options[cursor[student]]
                cursor[student] += 1
                proposals += 1
                rank = lecturer_ranks.get(lecturer, {}).get(student)
                if rank is None:
                    rejections.append(
                        Rejection(student, lecturer, rounds, RejectionReason.NOT_ACCEPTABLE)
                    )
                    continue
                key = (rank, order_index[student])
                if len(held[lecturer]) < capacity[lecturer]:
                    held[lecturer].append((key, student))
                    accepted_round[student] = rounds
                    break
                worst_key, worst_student = max(held[lecturer], key=lambda item: item[0])
                if key < worst_key:
                    held[lecturer].remove((worst_key, worst_student))
                    held[lecturer].append((key, student))
                    accepted_round[student] = rounds
                    rejections.append(
                        Rejection(worst_student, lecturer, rounds, RejectionReason.OUTRANKED)
                    )
                    queue.append(worst_student)
                    break
                rejections.append(Rejection(student, lecturer, rounds, RejectionReason.OUTRANKED))

    assignments: list[Assignment] = []
    # Peringkat yang dicatat adalah peringkat asli dosen, bukan peringkat sintetis
    # hasil APPEND: auditor harus bisa membedakan "diranking dosen" vs "diterima di dasar daftar".
    for student, lecturer in locked.items():
        assignments.append(
            Assignment(
                student_rank=student_ranks.get(student, {}).get(lecturer),
                lecturer_rank=lecturer_ranks_asli.get(lecturer, {}).get(student),
                round_number=0,
                student_id=student,
                lecturer_id=lecturer,
                is_locked=True,
            )
        )
    for lecturer, holders in held.items():
        for _key, student in sorted(holders, key=lambda item: item[0]):
            assignments.append(
                Assignment(
                    student_rank=student_ranks[student].get(lecturer),
                    lecturer_rank=lecturer_ranks_asli.get(lecturer, {}).get(student),
                    round_number=accepted_round[student],
                    student_id=student,
                    lecturer_id=lecturer,
                )
            )
    assignments.sort(
        key=lambda a: (not a.is_locked, order_index.get(a.student_id, -1), str(a.student_id))
    )
    assigned = {a.student_id for a in assignments}
    return MatchingResult(
        assignments=tuple(assignments),
        unmatched=tuple(student for student in order if student not in assigned),
        rounds=rounds,
        proposal_count=proposals,
        rejections=tuple(rejections),
    )