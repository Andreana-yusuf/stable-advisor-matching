from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Dosen(TimestampMixin, Base):
    __tablename__ = "dosen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nidn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    bidang_keahlian: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    kuota: Mapped[list["KuotaDosen"]] = relationship(back_populates="dosen")


class KuotaDosen(TimestampMixin, Base):
    """Kuota bersifat per periode: dosen yang sama bisa berbeda kuota antar tahun."""

    __tablename__ = "kuota_dosen"
    __table_args__ = (
        UniqueConstraint("periode_id", "dosen_id", name="uq_kuota_periode_dosen"),
        CheckConstraint("kuota >= 0", name="kuota_non_negatif"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periode_id: Mapped[int] = mapped_column(
        ForeignKey("periode.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dosen_id: Mapped[int] = mapped_column(
        ForeignKey("dosen.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kuota: Mapped[int] = mapped_column(Integer, nullable=False)

    periode: Mapped["Periode"] = relationship(back_populates="kuota_dosen")  # noqa: F821
    dosen: Mapped["Dosen"] = relationship(back_populates="kuota")