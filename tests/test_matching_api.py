from __future__ import annotations

from collections import Counter

from sqlalchemy import delete, select

from app.models import Alokasi, AlokasiStatus, KuotaDosen, Periode, PeriodeStatus
from tests.conftest import Pasar, eksekusi, isi_preferensi


def test_execute_tanpa_api_key_ditolak(client, pasar: Pasar):
    respons = client.post(
        "/api/matching/execute", json={"periode_id": pasar.periode_id, "tahap": "utama"}
    )
    assert respons.status_code == 401


def test_execute_dengan_api_key_salah_ditolak(client, pasar: Pasar):
    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "utama"},
        headers={"X-API-Key": "kunci-salah"},
    )
    assert respons.status_code == 401


def test_execute_utama_menghasilkan_alokasi_stabil(client, db, pasar: Pasar, admin_headers):
    m1, m2, m3, m4, m5 = pasar.mahasiswa_ids
    d1, d2, d3 = pasar.dosen_ids
    isi_preferensi(
        client,
        pasar,
        mahasiswa={m1: [d1, d2], m2: [d1, d3], m3: [d2, d1], m4: [d3, d1], m5: [d1]},
        dosen={d1: [m1, m2, m5, m3], d2: [m3, m1], d3: [m4, m2]},
    )

    hasil = eksekusi(
        client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama"}
    )

    assert hasil["verifikasi"]["stabil"] is True
    assert hasil["verifikasi"]["jumlah_blocking_pair"] == 0
    assert hasil["verifikasi"]["pelanggaran_kuota"] == []
    assert hasil["tersimpan"] is True
    assert hasil["jumlah_peserta"] == 5
    assert hasil["jumlah_alokasi_baru"] == 4  # total kuota 2+1+1
    assert len(hasil["mahasiswa_tidak_teralokasi"]) == 1

    rows = db.scalars(select(Alokasi).where(Alokasi.periode_id == pasar.periode_id)).all()
    assert len(rows) == 4
    assert all(r.status is AlokasiStatus.TERKUNCI for r in rows)
    terisi = Counter(r.dosen_id for r in rows)
    for dosen_id, jumlah in terisi.items():
        assert jumlah <= pasar.kuota[dosen_id]
    assert db.get(Periode, pasar.periode_id).status is PeriodeStatus.TERKUNCI


def test_dry_run_tidak_menyimpan_apapun(client, db, pasar: Pasar, admin_headers):
    m1, d1 = pasar.mahasiswa_ids[0], pasar.dosen_ids[0]
    isi_preferensi(client, pasar, mahasiswa={m1: [d1]}, dosen={d1: [m1]})

    hasil = eksekusi(
        client,
        admin_headers,
        {"periode_id": pasar.periode_id, "tahap": "utama", "dry_run": True},
    )

    assert hasil["dry_run"] is True
    assert hasil["tersimpan"] is False
    assert hasil["jumlah_alokasi_baru"] == 1
    assert db.scalars(select(Alokasi)).all() == []
    assert db.get(Periode, pasar.periode_id).status is PeriodeStatus.OPEN


def test_kunci_false_menyimpan_tentatif_dan_bisa_diulang(client, db, pasar: Pasar, admin_headers):
    m1, m2, d1 = pasar.mahasiswa_ids[:2] + [pasar.dosen_ids[0]]
    isi_preferensi(client, pasar, mahasiswa={m1: [d1], m2: [d1]}, dosen={d1: [m2, m1]})

    pertama = eksekusi(
        client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama", "kunci": False}
    )
    assert pertama["alokasi_baru"][0]["terkunci"] is False
    assert db.get(Periode, pasar.periode_id).status is PeriodeStatus.TENTATIF
    assert db.scalars(select(Alokasi).where(Alokasi.status == AlokasiStatus.TENTATIF)).all()

    kedua = eksekusi(
        client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama", "kunci": True}
    )
    assert kedua["jumlah_alokasi_baru"] == 2
    rows = db.scalars(select(Alokasi).where(Alokasi.periode_id == pasar.periode_id)).all()
    assert len(rows) == 2  # baris tentatif lama diganti, bukan diduplikasi
    assert all(r.status is AlokasiStatus.TERKUNCI for r in rows)


def test_execute_utama_kedua_kali_ditolak_setelah_terkunci(client, pasar: Pasar, admin_headers):
    m1, d1 = pasar.mahasiswa_ids[0], pasar.dosen_ids[0]
    isi_preferensi(client, pasar, mahasiswa={m1: [d1]}, dosen={d1: [m1]})
    eksekusi(client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama"})

    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "utama"},
        headers=admin_headers,
    )
    assert respons.status_code == 409
    assert "susulan" in respons.json()["detail"]


def test_execute_tanpa_kuota_ditolak(client, db, pasar: Pasar, admin_headers):
    db.execute(delete(KuotaDosen).where(KuotaDosen.periode_id == pasar.periode_id))
    db.commit()
    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "utama"},
        headers=admin_headers,
    )
    assert respons.status_code == 409
    assert "kuota" in respons.json()["detail"]


def test_execute_tanpa_preferensi_mahasiswa_ditolak(client, pasar: Pasar, admin_headers):
    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "utama"},
        headers=admin_headers,
    )
    assert respons.status_code == 409
    assert "preferensi" in respons.json()["detail"]


def test_execute_periode_tak_dikenal_404(client, admin_headers):
    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": 424242, "tahap": "utama"},
        headers=admin_headers,
    )
    assert respons.status_code == 404


def _pasar_utama_siap_susulan(client, pasar: Pasar, admin_headers) -> dict[int, int]:
    m1, m2, m3 = pasar.mahasiswa_ids[:3]
    d1, d2, _ = pasar.dosen_ids
    isi_preferensi(
        client,
        pasar,
        mahasiswa={m1: [d1], m2: [d1], m3: [d2]},
        dosen={d1: [m1, m2, m3], d2: [m3]},
    )
    eksekusi(client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama"})
    return {m1: d1, m2: d1, m3: d2}


def test_susulan_mengisi_sisa_kuota_tanpa_mengubah_kunci(client, db, pasar: Pasar, admin_headers):
    terkunci_awal = _pasar_utama_siap_susulan(client, pasar, admin_headers)
    m4 = pasar.mahasiswa_ids[3]
    d3 = pasar.dosen_ids[2]
    isi_preferensi(client, pasar, mahasiswa={m4: [d3, pasar.dosen_ids[0]]}, dosen={})

    hasil = eksekusi(
        client,
        admin_headers,
        {"periode_id": pasar.periode_id, "tahap": "susulan", "mahasiswa_ids": [m4]},
    )

    assert hasil["verifikasi"]["stabil"] is True
    assert hasil["jumlah_alokasi_terkunci_dipertahankan"] == 3
    assert hasil["jumlah_alokasi_baru"] == 1
    assert hasil["alokasi_baru"][0]["mahasiswa_id"] == m4
    assert hasil["alokasi_baru"][0]["dosen_id"] == d3
    assert hasil["alokasi_baru"][0]["peringkat_dosen"] is None  # diterima lewat kebijakan append

    rows = db.scalars(select(Alokasi).where(Alokasi.periode_id == pasar.periode_id)).all()
    assert len(rows) == 4
    for mahasiswa_id, dosen_id in terkunci_awal.items():
        baris = next(r for r in rows if r.mahasiswa_id == mahasiswa_id)
        assert baris.dosen_id == dosen_id, "alokasi terkunci berubah"
    assert Counter(r.dosen_id for r in rows)[d3] <= pasar.kuota[d3]


def test_susulan_otomatis_memilih_mahasiswa_belum_teralokasi(client, pasar: Pasar, admin_headers):
    _pasar_utama_siap_susulan(client, pasar, admin_headers)
    m4, m5 = pasar.mahasiswa_ids[3:]
    d3 = pasar.dosen_ids[2]
    isi_preferensi(client, pasar, mahasiswa={m4: [d3], m5: [d3]}, dosen={})

    hasil = eksekusi(
        client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "susulan"}
    )

    assert hasil["jumlah_peserta"] == 2
    assert hasil["jumlah_alokasi_baru"] == 1  # sisa kuota d3 hanya 1
    assert len(hasil["mahasiswa_tidak_teralokasi"]) == 1
    assert hasil["verifikasi"]["stabil"] is True


def test_susulan_kebijakan_reject_menolak_yang_tak_diranking(client, pasar: Pasar, admin_headers):
    _pasar_utama_siap_susulan(client, pasar, admin_headers)
    m4, d3 = pasar.mahasiswa_ids[3], pasar.dosen_ids[2]
    isi_preferensi(client, pasar, mahasiswa={m4: [d3]}, dosen={})

    hasil = eksekusi(
        client,
        admin_headers,
        {
            "periode_id": pasar.periode_id,
            "tahap": "susulan",
            "kebijakan_tak_terperingkat": "reject",
        },
    )

    assert hasil["jumlah_alokasi_baru"] == 0
    assert hasil["mahasiswa_tidak_teralokasi"] == [m4]


def test_susulan_menolak_mahasiswa_yang_sudah_terkunci(client, pasar: Pasar, admin_headers):
    terkunci_awal = _pasar_utama_siap_susulan(client, pasar, admin_headers)
    m1 = next(iter(terkunci_awal))
    respons = client.post(
        "/api/matching/execute",
        json={
            "periode_id": pasar.periode_id,
            "tahap": "susulan",
            "mahasiswa_ids": [m1],
        },
        headers=admin_headers,
    )
    assert respons.status_code == 409
    assert "terkunci" in respons.json()["detail"]


def test_susulan_menolak_mahasiswa_tanpa_preferensi(client, pasar: Pasar, admin_headers):
    _pasar_utama_siap_susulan(client, pasar, admin_headers)
    respons = client.post(
        "/api/matching/execute",
        json={
            "periode_id": pasar.periode_id,
            "tahap": "susulan",
            "mahasiswa_ids": [pasar.mahasiswa_ids[4]],
        },
        headers=admin_headers,
    )
    assert respons.status_code == 422
    assert "preferensi" in respons.json()["detail"]


def test_susulan_sebelum_utama_ditolak(client, pasar: Pasar, admin_headers):
    respons = client.post(
        "/api/matching/execute",
        json={"periode_id": pasar.periode_id, "tahap": "susulan"},
        headers=admin_headers,
    )
    assert respons.status_code == 409


def test_susulan_dry_run_tidak_menyimpan(client, db, pasar: Pasar, admin_headers):
    _pasar_utama_siap_susulan(client, pasar, admin_headers)
    m4, d3 = pasar.mahasiswa_ids[3], pasar.dosen_ids[2]
    isi_preferensi(client, pasar, mahasiswa={m4: [d3]}, dosen={})

    hasil = eksekusi(
        client,
        admin_headers,
        {"periode_id": pasar.periode_id, "tahap": "susulan", "dry_run": True},
    )

    assert hasil["tersimpan"] is False
    assert hasil["jumlah_alokasi_baru"] == 1
    rows = db.scalars(select(Alokasi).where(Alokasi.periode_id == pasar.periode_id)).all()
    assert len(rows) == 3