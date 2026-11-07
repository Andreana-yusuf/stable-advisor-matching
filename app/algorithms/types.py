"""Tipe data hasil algoritma. Bebas dependensi framework/DB agar bisa diuji secara terisolasi."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Hashable

StudentId = Hashable
LecturerId = Hashable


class UnrankedPolicy(str, Enum):
    """Sikap dosen terhadap mahasiswa yang tidak ada di daftar preferensinya."""

    REJECT = "reject"
    APPEND = "append"


class RejectionReason(str, Enum):
    NOT_ACCEPTABLE = "tidak_acceptable"
    OUTRANKED = "kalah_peringkat"


@dataclass(frozen=True, slots=True)
class Assignment:
    student_id: StudentId
    lecturer_id: LecturerId
    student_rank: int | None
    lecturer_rank: int | None
    round_number: int
    is_locked: bool = False


@dataclass(frozen=True, slots=True)
class Rejection:
    student_id: StudentId
    lecturer_id: LecturerId
    round_number: int
    reason: RejectionReason


@dataclass(frozen=True, slots=True)
class MatchingResult:
    assignments: tuple[Assignment, ...]
    unmatched: tuple[StudentId, ...]
    rounds: int
    proposal_count: int
    rejections: tuple[Rejection, ...] = ()

    @property
    def student_to_lecturer(self) -> dict[StudentId, LecturerId]:
        return {a.student_id: a.lecturer_id for a in self.assignments}

    @property
    def lecturer_to_students(self) -> dict[LecturerId, tuple[StudentId, ...]]:
        grouped: dict[LecturerId, list[StudentId]] = {}
        for a in self.assignments:
            grouped.setdefault(a.lecturer_id, []).append(a.student_id)
        return {lecturer: tuple(students) for lecturer, students in grouped.items()}

    @property
    def locked(self) -> dict[StudentId, LecturerId]:
        return {a.student_id: a.lecturer_id for a in self.assignments if a.is_locked}

    @property
    def newly_assigned(self) -> tuple[Assignment, ...]:
        return tuple(a for a in self.assignments if not a.is_locked)


@dataclass(frozen=True, slots=True)
class BlockingPair:
    student_id: StudentId
    lecturer_id: LecturerId
    student_rank: int
    lecturer_rank: int
    reason: str
    displaced_student_id: StudentId | None = None


@dataclass(frozen=True, slots=True)
class QuotaViolation:
    lecturer_id: LecturerId
    assigned: int
    quota: int


@dataclass(frozen=True, slots=True)
class RationalityViolation:
    student_id: StudentId
    lecturer_id: LecturerId
    reason: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    blocking_pairs: tuple[BlockingPair, ...]
    quota_violations: tuple[QuotaViolation, ...]
    rationality_violations: tuple[RationalityViolation, ...]

    @property
    def is_stable(self) -> bool:
        return not (self.blocking_pairs or self.quota_violations or self.rationality_violations)

    @property
    def is_valid(self) -> bool:
        return not (self.quota_violations or self.rationality_violations)