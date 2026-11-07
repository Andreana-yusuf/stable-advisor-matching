"""Error domain yang dipetakan ke HTTP status oleh exception handler di main."""

from __future__ import annotations


class DomainError(Exception):
    status_code = 400
    kode = "domain_error"

    def __init__(self, pesan: str, *, detail: object | None = None) -> None:
        super().__init__(pesan)
        self.pesan = pesan
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404
    kode = "tidak_ditemukan"


class ConflictError(DomainError):
    status_code = 409
    kode = "konflik"


class InputError(DomainError):
    status_code = 422
    kode = "input_tidak_valid"


class MatchingTidakStabilError(DomainError):
    status_code = 500
    kode = "hasil_tidak_stabil"