from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class PreferensiMahasiswa(TimestampMixin, Base):
    """Satu baris = satu pilihan dosen pada peringkat `urutan` (1 = paling disukai)."""

    __tablename__ = "preferensi_mahasiswa"
    __table_args__ = (
        UniqueConstraint("periode_id", "mahasiswa_id", "urutan", name="uq_preferensi_mhs_urutan"),
        UniqueConstraint("periode_id", "mahasiswa_id", "dosen_id", name="uq_preferensi_mhs_dosen"),
        CheckConstraint("urutan > 0", name="urutan_positif"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periode_id: Mapped[int] = mapped_column(
        ForeignKey("periode.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mahasiswa_id: Mapped[int] = mapped_column(
        ForeignKey("mahasiswa.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dosen_id: Mapped[int] = mapped_column(
        ForeignKey("dosen.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    urutan: Mapped[int] = mapped_column(Integer, nullable=False)
    # Dipertahankan saat mahasiswa merevisi daftar, supaya status late-register
    # tidak berubah hanya karena ia menyunting preferensi setelah tenggat.
    submit_pertama_pada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PreferensiDosen(TimestampMixin, Base):
    """Satu baris = satu mahasiswa yang bersedia dibimbing, pada peringkat `urutan`."""

    __tablename__ = "preferensi_dosen"
    __table_args__ = (
        UniqueConstraint("periode_id", "dosen_id", "urutan", name="uq_preferensi_dosen_urutan"),
        UniqueConstraint("periode_id", "dosen_id", "mahasiswa_id", name="uq_preferensi_dosen_mhs"),
        CheckConstraint("urutan > 0", name="urutan_positif"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periode_id: Mapped[int] = mapped_column(
        ForeignKey("periode.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dosen_id: Mapped[int] = mapped_column(
        ForeignKey("dosen.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mahasiswa_id: Mapped[int] = mapped_column(
        ForeignKey("mahasiswa.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    urutan: Mapped[int] = mapped_column(Integer, nullable=False)