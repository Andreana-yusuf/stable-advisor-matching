from __future__ import annotations

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import AlokasiStatus, Tahap, enum_values


class Alokasi(TimestampMixin, Base):
    __tablename__ = "alokasi"
    __table_args__ = (
        UniqueConstraint("periode_id", "mahasiswa_id", name="uq_alokasi_periode_mahasiswa"),
        CheckConstraint("ronde >= 0", name="ronde_non_negatif"),
        CheckConstraint(
            "peringkat_mahasiswa IS NULL OR peringkat_mahasiswa > 0", name="peringkat_mhs_positif"
        ),
        CheckConstraint(
            "peringkat_dosen IS NULL OR peringkat_dosen > 0", name="peringkat_dosen_positif"
        ),
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
    tahap: Mapped[Tahap] = mapped_column(
        Enum(
            Tahap,
            name="alokasi_tahap",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    status: Mapped[AlokasiStatus] = mapped_column(
        Enum(
            AlokasiStatus,
            name="alokasi_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AlokasiStatus.TENTATIF,
        server_default=AlokasiStatus.TENTATIF.value,
    )
    peringkat_mahasiswa: Mapped[int | None] = mapped_column(Integer)
    peringkat_dosen: Mapped[int | None] = mapped_column(Integer)
    ronde: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    periode: Mapped["Periode"] = relationship(back_populates="alokasi")  # noqa: F821
    mahasiswa: Mapped["Mahasiswa"] = relationship()  # noqa: F821
    dosen: Mapped["Dosen"] = relationship()  # noqa: F821