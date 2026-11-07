from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Dosen, KuotaDosen, Mahasiswa, Periode, PeriodeStatus


@dataclass
class Pasar:
    periode_id: int
    dosen_ids: list[int]
    mahasiswa_ids: list[int]
    kuota: dict[int, int]


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-API-Key": settings.admin_api_key}


@pytest.fixture
def pasar(db) -> Pasar:
    sekarang = datetime.now(timezone.utc)
    periode = Periode(
        kode="2026-GANJIL",
        nama="Periode 2026 Ganjil",
        status=PeriodeStatus.OPEN,
        tanggal_mulai=date(2026, 9, 1),
        tanggal_selesai=date(2027, 1, 31),
        batas_preferensi=sekarang + timedelta(days=7),
        max_preferensi=3,
    )
    db.add(periode)
    db.flush()

    dosen = [
        Dosen(nidn=f"000000000{i}", nama=f"Dosen {i}", email=f"dosen{i}@kampus.ac.id")
        for i in range(1, 4)
    ]
    mahasiswa = [
        Mahasiswa(
            nim=f"221000{i}", nama=f"Mahasiswa {i}", email=f"mhs{i}@kampus.ac.id", angkatan=2022
        )
        for i in range(1, 6)
    ]
    db.add_all(dosen + mahasiswa)
    db.flush()

    kuota = {dosen[0].id: 2, dosen[1].id: 1, dosen[2].id: 1}
    db.add_all(
        KuotaDosen(periode_id=periode.id, dosen_id=dosen_id, kuota=jumlah)
        for dosen_id, jumlah in kuota.items()
    )
    db.commit()
    return Pasar(periode.id, [d.id for d in dosen], [m.id for m in mahasiswa], kuota)


def isi_preferensi(
    client: TestClient,
    pasar: Pasar,
    *,
    mahasiswa: dict[int, list[int]],
    dosen: dict[int, list[int]],
) -> None:
    for mahasiswa_id, dosen_ids in mahasiswa.items():
        respons = client.post(
            "/api/preferensi",
            json={
                "periode_id": pasar.periode_id,
                "mahasiswa_id": mahasiswa_id,
                "dosen_ids": dosen_ids,
            },
        )
        assert respons.status_code == 201, respons.text
    for dosen_id, mahasiswa_ids in dosen.items():
        respons = client.post(
            "/api/preferensi/dosen",
            json={
                "periode_id": pasar.periode_id,
                "dosen_id": dosen_id,
                "mahasiswa_ids": mahasiswa_ids,
            },
        )
        assert respons.status_code == 201, respons.text


def eksekusi(client: TestClient, headers: dict[str, str], payload: dict) -> dict:
    respons = client.post("/api/matching/execute", json=payload, headers=headers)
    assert respons.status_code == 200, respons.text
    return respons.json()