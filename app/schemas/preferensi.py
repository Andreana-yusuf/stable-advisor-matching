from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

PositiveId = Annotated[int, Field(gt=0)]


class PreferensiMahasiswaInput(BaseModel):
    periode_id: PositiveId
    mahasiswa_id: PositiveId
    dosen_ids: list[PositiveId] = Field(min_length=1, description="Urutan index 0 = pilihan pertama")

    @field_validator("dosen_ids")
    @classmethod
    def tanpa_duplikat(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("dosen_ids tidak boleh memuat dosen yang sama lebih dari sekali")
        return value


class PreferensiDosenInput(BaseModel):
    periode_id: PositiveId
    dosen_id: PositiveId
    mahasiswa_ids: list[PositiveId] = Field(min_length=1, description="Urutan index 0 = paling prioritas")

    @field_validator("mahasiswa_ids")
    @classmethod
    def tanpa_duplikat(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("mahasiswa_ids tidak boleh memuat mahasiswa yang sama lebih dari sekali")
        return value


class PreferensiMahasiswaOutput(BaseModel):
    periode_id: int
    mahasiswa_id: int
    dosen_ids: list[int]
    jumlah: int
    late_register: bool


class PreferensiDosenOutput(BaseModel):
    periode_id: int
    dosen_id: int
    mahasiswa_ids: list[int]
    jumlah: int