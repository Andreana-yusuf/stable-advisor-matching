from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import PeriodeStatus, enum_values


class Periode(TimestampMixin, Base):
    __tablename__ = "periode"
    __table_args__ = (
        CheckConstraint("tanggal_selesai >= tanggal_mulai", name="rentang_tanggal"),
        CheckConstraint("max_preferensi > 0", name="max_preferensi_positif"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    nama: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[PeriodeStatus] = mapped_column(
        Enum(
            PeriodeStatus,
            name="periode_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=PeriodeStatus.DRAFT,
        server_default=PeriodeStatus.DRAFT.value,
    )
    tanggal_mulai: Mapped[date] = mapped_column(Date, nullable=False)
    tanggal_selesai: Mapped[date] = mapped_column(Date, nullable=False)
    batas_preferensi: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_preferensi: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )

    kuota_dosen: Mapped[list["KuotaDosen"]] = relationship(  # noqa: F821
        back_populates="periode", cascade="all, delete-orphan", passive_deletes=True
    )
    alokasi: Mapped[list["Alokasi"]] = relationship(  # noqa: F821
        back_populates="periode", cascade="all, delete-orphan", passive_deletes=True
    )