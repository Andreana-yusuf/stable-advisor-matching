"""Enum domain yang dipakai bersama oleh model, schema, dan service."""

from __future__ import annotations

from enum import Enum


class PeriodeStatus(str, Enum):
    DRAFT = "draft"
    OPEN = "open"
    TENTATIF = "tentatif"
    TERKUNCI = "terkunci"
    SUSULAN = "susulan"
    SELESAI = "selesai"


class AlokasiStatus(str, Enum):
    TENTATIF = "tentatif"
    TERKUNCI = "terkunci"


class Tahap(str, Enum):
    UTAMA = "utama"
    SUSULAN = "susulan"


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """Tanpa ini SQLAlchemy menyimpan .name ('DRAFT'), bukan .value ('draft')."""
    return [member.value for member in enum_cls]