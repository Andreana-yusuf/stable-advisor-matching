"""Referens brute-force untuk pasar kecil: membuktikan student-optimality, bukan cuma stabilitas."""

from __future__ import annotations

import itertools
from collections import Counter

from app.algorithms import LecturerId, StudentId, find_blocking_pairs


def semua_matching_stabil(
    preferensi_mahasiswa: dict[StudentId, list[LecturerId]],
    preferensi_dosen: dict[LecturerId, list[StudentId]],
    kuota: dict[LecturerId, int],
) -> list[dict[StudentId, LecturerId]]:
    """Enumerasi seluruh alokasi layak, saring yang stabil. Hanya untuk pasar sangat kecil."""
    students = list(preferensi_mahasiswa)
    pilihan = [list(preferensi_mahasiswa[s]) + [None] for s in students]
    stabil: list[dict[StudentId, LecturerId]] = []
    for kombinasi in itertools.product(*pilihan):
        matching = {s: l for s, l in zip(students, kombinasi) if l is not None}
        terisi = Counter(matching.values())
        if any(jumlah > kuota.get(dosen, 0) for dosen, jumlah in terisi.items()):
            continue
        if any(m not in preferensi_dosen.get(d, []) for m, d in matching.items()):
            continue
        if not find_blocking_pairs(matching, preferensi_mahasiswa, preferensi_dosen, kuota):
            stabil.append(matching)
    return stabil


def pilihan_terbaik_student_optimal(
    stabil: list[dict[StudentId, LecturerId]],
    preferensi_mahasiswa: dict[StudentId, list[LecturerId]],
) -> dict[StudentId, LecturerId | None]:
    """Untuk tiap mahasiswa, ambil peringkat terbaik yang muncul di suatu matching stabil."""
    terbaik: dict[StudentId, LecturerId | None] = {}
    for student, ranking in preferensi_mahasiswa.items():
        kandidat = [matching.get(student) for matching in stabil]
        terbaik[student] = min(
            (d for d in kandidat if d is not None),
            key=lambda d: ranking.index(d),
            default=None,
        )
    return terbaik