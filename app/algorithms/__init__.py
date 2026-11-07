"""Inti algoritma alokasi: pure function, tanpa dependensi FastAPI/SQLAlchemy."""

from app.algorithms.gale_shapley import gale_shapley, match_late_registrants, residual_capacity
from app.algorithms.types import (
    Assignment,
    BlockingPair,
    LecturerId,
    MatchingResult,
    QuotaViolation,
    Rejection,
    RejectionReason,
    StudentId,
    UnrankedPolicy,
    VerificationReport,
)
from app.algorithms.validation import (
    find_blocking_pairs,
    find_quota_violations,
    find_rationality_violations,
    verify_matching,
)

__all__ = [
    "Assignment",
    "BlockingPair",
    "LecturerId",
    "MatchingResult",
    "QuotaViolation",
    "Rejection",
    "RejectionReason",
    "StudentId",
    "UnrankedPolicy",
    "VerificationReport",
    "find_blocking_pairs",
    "find_quota_violations",
    "find_rationality_violations",
    "gale_shapley",
    "match_late_registrants",
    "residual_capacity",
    "verify_matching",
]