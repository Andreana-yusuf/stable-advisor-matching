"""Normalisasi input preferensi: validasi, pemetaan peringkat, dan kapasitas sisa."""

from __future__ import annotations

from typing import Hashable, Iterable, Mapping, Sequence

from app.algorithms.types import LecturerId, StudentId, UnrankedPolicy

RankMap = dict[Hashable, dict[Hashable, int]]


def build_rank_map(preferences: Mapping[Hashable, Sequence[Hashable]], *, side: str) -> RankMap:
    """Ubah daftar terurut menjadi peta peringkat 1-based; menolak duplikat."""
    ranks: RankMap = {}
    for owner, ranking in preferences.items():
        per_owner: dict[Hashable, int] = {}
        for position, target in enumerate(ranking, start=1):
            if target in per_owner:
                raise ValueError(f"Preferensi {side} {owner!r} memuat {target!r} lebih dari sekali")
            per_owner[target] = position
        ranks[owner] = per_owner
    return ranks


def validate_quotas(quotas: Mapping[LecturerId, int]) -> None:
    for lecturer, quota in quotas.items():
        if not isinstance(quota, int) or isinstance(quota, bool):
            raise TypeError(f"Kuota dosen {lecturer!r} harus integer, bukan {type(quota).__name__}")
        if quota < 0:
            raise ValueError(f"Kuota dosen {lecturer!r} tidak boleh negatif: {quota}")


def residual_capacity(
    quotas: Mapping[LecturerId, int], locked: Mapping[StudentId, LecturerId]
) -> dict[LecturerId, int]:
    """Kuota dikurangi alokasi terkunci. Alokasi terkunci tidak boleh melampaui kuota."""
    validate_quotas(quotas)
    used: dict[LecturerId, int] = {}
    for student, lecturer in locked.items():
        if lecturer not in quotas:
            raise ValueError(f"Alokasi terkunci {student!r} menunjuk dosen tak dikenal: {lecturer!r}")
        used[lecturer] = used.get(lecturer, 0) + 1
    residual: dict[LecturerId, int] = {}
    for lecturer, quota in quotas.items():
        taken = used.get(lecturer, 0)
        if taken > quota:
            raise ValueError(f"Alokasi terkunci dosen {lecturer!r} ({taken}) melampaui kuota ({quota})")
        residual[lecturer] = quota - taken
    return residual


def extend_ranks(
    base: Mapping[LecturerId, Mapping[StudentId, int]],
    lecturers: Iterable[LecturerId],
    candidates: Sequence[StudentId],
    policy: UnrankedPolicy,
) -> dict[LecturerId, dict[StudentId, int]]:
    """Lengkapi peringkat dosen untuk kandidat tak terperingkat sesuai kebijakan.

    APPEND menaruh kandidat tak terperingkat di dasar daftar dengan urutan
    deterministik mengikuti `candidates`, sehingga hasil susulan tetap dapat
    direproduksi dan diuji kestabilannya terhadap preferensi yang sama.
    """
    extended: dict[LecturerId, dict[StudentId, int]] = {}
    for lecturer in lecturers:
        ranks = dict(base.get(lecturer, {}))
        if policy is UnrankedPolicy.APPEND:
            offset = len(ranks)
            for index, student in enumerate(candidates, start=1):
                if student not in ranks:
                    ranks[student] = offset + index
        extended[lecturer] = ranks
    return extended


def acceptable_choices(
    choices: Mapping[StudentId, Sequence[LecturerId]],
    capacity: Mapping[LecturerId, int],
) -> dict[StudentId, tuple[LecturerId, ...]]:
    """Buang pilihan dosen berkapasitas nol atau tak dikenal agar tidak membuang proposal."""
    filtered: dict[StudentId, tuple[LecturerId, ...]] = {}
    for student, ranking in choices.items():
        kept = tuple(lecturer for lecturer in ranking if capacity.get(lecturer, 0) > 0)
        unknown = [lecturer for lecturer in ranking if lecturer not in capacity]
        if unknown:
            raise ValueError(f"Preferensi mahasiswa {student!r} menunjuk dosen tak dikenal: {unknown!r}")
        filtered[student] = kept
    return filtered