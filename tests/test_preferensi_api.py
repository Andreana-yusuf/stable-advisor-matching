from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import Dosen, Periode, PreferensiDosen, PreferensiMahasiswa
from tests.conftest import Pasar, isi_preferensi


def test_input_preferensi_mahasiswa_tersimpan_berurutan(client, pasar: Pasar):
    d1, d2, d3 = pasar.dosen_ids
    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": pasar.periode_id,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": [d2, d1, d3],
        },
    )

    assert respons.status_code == 201, respons.text
    isi = respons.json()
    assert isi["dosen_ids"] == [d2, d1, d3]
    assert isi["jumlah"] == 3
    assert isi["late_register"] is False


def test_revisi_preferensi_mengganti_daftar_lama(client, db, pasar: Pasar):
    d1, d2, d3 = pasar.dosen_ids
    mahasiswa_id = pasar.mahasiswa_ids[0]
    for daftar in ([d1, d2], [d3, d2, d1]):
        respons = client.post(
            "/api/preferensi",
            json={
                "periode_id": pasar.periode_id,
                "mahasiswa_id": mahasiswa_id,
                "dosen_ids": daftar,
            },
        )
        assert respons.status_code == 201, respons.text

    jumlah = db.scalar(
        select(func.count())
        .select_from(PreferensiMahasiswa)
        .where(
            PreferensiMahasiswa.periode_id == pasar.periode_id,
            PreferensiMahasiswa.mahasiswa_id == mahasiswa_id,
        )
    )
    assert jumlah == 3
    assert respons.json()["dosen_ids"] == [d3, d2, d1]


def test_preferensi_duplikat_ditolak(client, pasar: Pasar):
    d1 = pasar.dosen_ids[0]
    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": pasar.periode_id,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": [d1, d1],
        },
    )
    assert respons.status_code == 422


def test_preferensi_melebihi_batas_periode_ditolak(client, pasar: Pasar):
    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": pasar.periode_id,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": pasar.dosen_ids + [999],
        },
    )
    assert respons.status_code == 422
    assert "batas periode" in respons.json()["detail"]


def test_preferensi_ke_dosen_tanpa_kuota_ditolak(client, db, pasar: Pasar):
    dari_luar = Dosen(
        nidn="9999999999", nama="Dosen Tanpa Kuota", email="tanpa@kampus.ac.id"
    )
    db.add(dari_luar)
    db.commit()

    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": pasar.periode_id,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": [dari_luar.id],
        },
    )
    assert respons.status_code == 422
    assert "kuota" in respons.json()["detail"]


def test_periode_tak_dikenal_menghasilkan_404(client, pasar: Pasar):
    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": 9999,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": [pasar.dosen_ids[0]],
        },
    )
    assert respons.status_code == 404
    assert respons.json()["kode"] == "tidak_ditemukan"


def test_submit_setelah_tenggat_ditandai_late_register(client, db, pasar: Pasar):
    periode = db.get(Periode, pasar.periode_id)
    periode.batas_preferensi = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    respons = client.post(
        "/api/preferensi",
        json={
            "periode_id": pasar.periode_id,
            "mahasiswa_id": pasar.mahasiswa_ids[0],
            "dosen_ids": [pasar.dosen_ids[0]],
        },
    )
    assert respons.status_code == 201, respons.text
    assert respons.json()["late_register"] is True


def test_revisi_tidak_mereset_waktu_submit_pertama(client, db, pasar: Pasar):
    periode = db.get(Periode, pasar.periode_id)
    periode.batas_preferensi = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    mahasiswa_id = pasar.mahasiswa_ids[0]
    payload = {
        "periode_id": pasar.periode_id,
        "mahasiswa_id": mahasiswa_id,
        "dosen_ids": [pasar.dosen_ids[0]],
    }
    assert client.post("/api/preferensi", json=payload).json()["late_register"] is True

    stmt = select(PreferensiMahasiswa.submit_pertama_pada).where(
        PreferensiMahasiswa.periode_id == pasar.periode_id,
        PreferensiMahasiswa.mahasiswa_id == mahasiswa_id,
    )
    submit_awal = db.scalars(stmt).first()

    payload["dosen_ids"] = [pasar.dosen_ids[1], pasar.dosen_ids[0]]
    respons = client.post("/api/preferensi", json=payload)

    assert respons.status_code == 201, respons.text
    # Status late dihitung terhadap tenggat, tapi waktu submit pertama harus tetap.
    assert db.scalars(stmt).first() == submit_awal
    assert respons.json()["late_register"] is True


def test_input_preferensi_dosen_tersimpan_berurutan(client, db, pasar: Pasar):
    d1 = pasar.dosen_ids[0]
    m1, m2, m3 = pasar.mahasiswa_ids[:3]
    respons = client.post(
        "/api/preferensi/dosen",
        json={"periode_id": pasar.periode_id, "dosen_id": d1, "mahasiswa_ids": [m3, m1, m2]},
    )

    assert respons.status_code == 201, respons.text
    assert respons.json()["mahasiswa_ids"] == [m3, m1, m2]
    urutan = db.scalars(
        select(PreferensiDosen.urutan)
        .where(PreferensiDosen.periode_id == pasar.periode_id, PreferensiDosen.dosen_id == d1)
        .order_by(PreferensiDosen.urutan)
    ).all()
    assert urutan == [1, 2, 3]


def test_preferensi_dosen_duplikat_ditolak(client, pasar: Pasar):
    m1 = pasar.mahasiswa_ids[0]
    respons = client.post(
        "/api/preferensi/dosen",
        json={
            "periode_id": pasar.periode_id,
            "dosen_id": pasar.dosen_ids[0],
            "mahasiswa_ids": [m1, m1],
        },
    )
    assert respons.status_code == 422


def test_preferensi_dosen_tanpa_kuota_ditolak(client, db, pasar: Pasar):
    dari_luar = Dosen(
        nidn="8888888888", nama="Dosen Baru", email="baru@kampus.ac.id"
    )
    db.add(dari_luar)
    db.commit()
    respons = client.post(
        "/api/preferensi/dosen",
        json={
            "periode_id": pasar.periode_id,
            "dosen_id": dari_luar.id,
            "mahasiswa_ids": [pasar.mahasiswa_ids[0]],
        },
    )
    assert respons.status_code == 422


def test_preferensi_terkunci_tidak_bisa_diubah(client, pasar: Pasar, admin_headers):
    m1, m2, m3 = pasar.mahasiswa_ids[:3]
    d1, d2, d3 = pasar.dosen_ids
    isi_preferensi(
        client, pasar, mahasiswa={m1: [d1], m2: [d1], m3: [d2]}, dosen={d1: [m1, m2, m3], d2: [m3]}
    )
    hasil = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "utama"},
        headers=admin_headers,
    )
    assert hasil.status_code == 200, hasil.text

    respons = client.post(
        "/api/preferensi",
        json={"periode_id": pasar.periode_id, "mahasiswa_id": m1, "dosen_ids": [d2]},
    )
    assert respons.status_code == 409
    assert "terkunci" in respons.json()["detail"]

    respons_dosen = client.post(
        "/api/preferensi/dosen",
        json={"periode_id": pasar.periode_id, "dosen_id": d1, "mahasiswa_ids": [m3, m2, m1]},
    )
    assert respons_dosen.status_code == 409