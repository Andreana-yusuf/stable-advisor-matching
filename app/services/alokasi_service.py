"""Query hasil alokasi untuk dibaca admin/dosen/mahasiswa."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alokasi, AlokasiStatus, Dosen, Mahasiswa, Tahap
from app.schemas.alokasi import AlokasiListResponse, AlokasiOutput
from app.services import repository as repo


def daftar_alokasi(
    db: Session,
    *,
    periode_id: int,
    mahasiswa_id: int | None = None,
    dosen_id: int | None = None,
    status: AlokasiStatus | None = None,
    tahap: Tahap | None = None,
    page: int = 1,
    page_size: int = 50,
) -> AlokasiListResponse:
    repo.ambil_periode(db, periode_id)

    kondisi = [Alokasi.periode_id == periode_id]
    if mahasiswa_id is not None:
        kondisi.append(Alokasi.mahasiswa_id == mahasiswa_id)
    if dosen_id is not None:
        kondisi.append(Alokasi.dosen_id == dosen_id)
    if status is not None:
        kondisi.append(Alokasi.status == status)
    if tahap is not None:
        kondisi.append(Alokasi.tahap == tahap)

    total = db.scalar(select(func.count()).select_from(Alokasi).where(*kondisi)) or 0
    rows = db.execute(
        select(Alokasi, Mahasiswa.nim, Mahasiswa.nama, Dosen.nidn, Dosen.nama)
        .join(Mahasiswa, Mahasiswa.id == Alokasi.mahasiswa_id)
        .join(Dosen, Dosen.id == Alokasi.dosen_id)
        .where(*kondisi)
        .order_by(Alokasi.dosen_id, Alokasi.mahasiswa_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AlokasiListResponse(
        data=[
            AlokasiOutput(
                id=a.id,
                periode_id=a.periode_id,
                mahasiswa_id=a.mahasiswa_id,
                nim=nim,
                nama_mahasiswa=nama_mahasiswa,
                dosen_id=a.dosen_id,
                nidn=nidn,
                nama_dosen=nama_dosen,
                tahap=a.tahap,
                status=a.status,
                peringkat_mahasiswa=a.peringkat_mahasiswa,
                peringkat_dosen=a.peringkat_dosen,
                ronde=a.ronde,
                dibuat_pada=a.created_at,
            )
            for a, nim, nama_mahasiswa, nidn, nama_dosen in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )