"""Validator hasil alokasi: blocking pair, kuota, dan rasionalitas individual.

Dipakai baik oleh unit test maupun oleh service sebelum hasil dipersist,
sehingga klaim "stabil" selalu diverifikasi terhadap preferensi yang sama.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from app.algorithms.preferences import build_rank_map, extend_ranks
from app.algorithms.types import (
    BlockingPair,
    LecturerId,
    QuotaViolation,
    RationalityViolation,
    StudentId,
    UnrankedPolicy,
    VerificationReport,
)

_INF = float("inf")


def find_blocking_pairs(
    matching: Mapping[StudentId, LecturerId],
    preferensi_mahasiswa: Mapping[StudentId, Sequence[LecturerId]],
    preferensi_dosen: Mapping[LecturerId, Sequence[StudentId]],
    kuota_dosen: Mapping[LecturerId, int],
    *,
    mahasiswa_terkunci: Sequence[StudentId] = (),
    kebijakan_tak_terperingkat: UnrankedPolicy = UnrankedPolicy.REJECT,
    urutan_pengusul: Sequence[StudentId] | None = None,
) -> tuple[BlockingPair, ...]:
    """Cari pasangan (mahasiswa, dosen) yang lebih memilih satu sama lain.

    Mahasiswa terkunci dilewati: kursinya dibekukan secara administratif dan
    tidak boleh digusur, jadi ia bukan bagian dari pasar yang diuji.
    """
    student_ranks = build_rank_map(preferensi_mahasiswa, side="mahasiswa")
    lecturer_ranks = build_rank_map(preferensi_dosen, side="dosen")
    locked = set(mahasiswa_terkunci)
    candidates = (
        tuple(urutan_pengusul)
        if urutan_pengusul is not None
        else tuple(s for s in preferensi_mahasiswa if s not in locked)
    )
    extended = extend_ranks(lecturer_ranks, kuota_dosen, candidates, kebijakan_tak_terperingkat)

    grouped: dict[LecturerId, list[StudentId]] = {}
    for student, lecturer in matching.items():
        grouped.setdefault(lecturer, []).append(student)

    blocks: list[BlockingPair] = []
    for student, ranking in student_ranks.items():
        if student in locked:
            continue
        current = matching.get(student)
        current_rank = ranking.get(current, _INF) if current is not None else _INF
        for lecturer, student_rank in ranking.items():
            if student_rank >= current_rank or lecturer not in kuota_dosen:
                continue
            lecturer_rank = extended.get(lecturer, {}).get(student)
            if lecturer_rank is None:
                continue
            assigned = grouped.get(lecturer, [])
            if len(assigned) < kuota_dosen[lecturer]:
                blocks.append(
                    BlockingPair(student, lecturer, student_rank, lecturer_rank, "kuota_tersisa")
                )
                continue
            displaceable = [
                (extended.get(lecturer, {}).get(other, _INF), other)
                for other in assigned
                if other not in locked
            ]
            if not displaceable:
                continue
            worst_rank, worst_student = max(displaceable, key=lambda item: item[0])
            if lecturer_rank < worst_rank:
                blocks.append(
                    BlockingPair(
                        student,
                        lecturer,
                        student_rank,
                        lecturer_rank,
                        "menggusur_penerima_terburuk",
                        worst_student,
                    )
                )
    blocks.sort(key=lambda b: (str(b.student_id), str(b.lecturer_id)))
    return tuple(blocks)


def find_quota_violations(
    matching: Mapping[StudentId, LecturerId], kuota_dosen: Mapping[LecturerId, int]
) -> tuple[QuotaViolation, ...]:
    grouped: dict[LecturerId, int] = {}
    for lecturer in matching.values():
        grouped[lecturer] = grouped.get(lecturer, 0) + 1
    violations = [
        QuotaViolation(lecturer, count, kuota_dosen[lecturer])
        for lecturer, count in grouped.items()
        if lecturer in kuota_dosen and count > kuota_dosen[lecturer]
    ]
    violations.extend(
        QuotaViolation(lecturer, count, 0)
        for lecturer, count in grouped.items()
        if lecturer not in kuota_dosen
    )
    violations.sort(key=lambda v: str(v.lecturer_id))
    return tuple(violations)


def find_rationality_violations(
    matching: Mapping[StudentId, LecturerId],
    preferensi_mahasiswa: Mapping[StudentId, Sequence[LecturerId]],
    preferensi_dosen: Mapping[LecturerId, Sequence[StudentId]],
    kuota_dosen: Mapping[LecturerId, int],
    *,
    kebijakan_tak_terperingkat: UnrankedPolicy = UnrankedPolicy.REJECT,
    urutan_pengusul: Sequence[StudentId] | None = None,
) -> tuple[RationalityViolation, ...]:
    student_ranks = build_rank_map(preferensi_mahasiswa, side="mahasiswa")
    lecturer_ranks = build_rank_map(preferensi_dosen, side="dosen")
    candidates = (
        tuple(urutan_pengusul) if urutan_pengusul is not None else tuple(matching)
    )
    extended = extend_ranks(lecturer_ranks, kuota_dosen, candidates, kebijakan_tak_terperingkat)
    violations: list[RationalityViolation] = []
    for student, lecturer in matching.items():
        if lecturer not in student_ranks.get(student, {}):
            violations.append(
                RationalityViolation(student, lecturer, "dosen tidak ada di preferensi mahasiswa")
            )
        if student not in extended.get(lecturer, {}):
            violations.append(
                RationalityViolation(student, lecturer, "mahasiswa tidak diterima dosen")
            )
    violations.sort(key=lambda v: (str(v.student_id), str(v.lecturer_id), v.reason))
    return tuple(violations)


def verify_matching(
    matching: Mapping[StudentId, LecturerId],
    preferensi_mahasiswa: Mapping[StudentId, Sequence[LecturerId]],
    preferensi_dosen: Mapping[LecturerId, Sequence[StudentId]],
    kuota_dosen: Mapping[LecturerId, int],
    *,
    mahasiswa_terkunci: Sequence[StudentId] = (),
    kebijakan_tak_terperingkat: UnrankedPolicy = UnrankedPolicy.REJECT,
    urutan_pengusul: Sequence[StudentId] | None = None,
) -> VerificationReport:
    return VerificationReport(
        blocking_pairs=find_blocking_pairs(
            matching,
            preferensi_mahasiswa,
            preferensi_dosen,
            kuota_dosen,
            mahasiswa_terkunci=mahasiswa_terkunci,
            kebijakan_tak_terperingkat=kebijakan_tak_terperingkat,
            urutan_pengusul=urutan_pengusul,
        ),
        quota_violations=find_quota_violations(matching, kuota_dosen),
        rationality_violations=find_rationality_violations(
            matching,
            preferensi_mahasiswa,
            preferensi_dosen,
            kuota_dosen,
            kebijakan_tak_terperingkat=kebijakan_tak_terperingkat,
            urutan_pengusul=urutan_pengusul,
        ),
    )