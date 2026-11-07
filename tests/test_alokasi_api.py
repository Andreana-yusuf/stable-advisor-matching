from __future__ import annotations

from tests.conftest import Pasar, eksekusi, isi_preferensi


def _siapkan_hasil(client, pasar: Pasar, admin_headers) -> None:
    m1, m2, m3 = pasar.mahasiswa_ids[:3]
    d1, d2, _ = pasar.dosen_ids
    isi_preferensi(
        client,
        pasar,
        mahasiswa={m1: [d1, d2], m2: [d1], m3: [d2]},
        dosen={d1: [m1, m2, m3], d2: [m3, m1]},
    )
    eksekusi(client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama"})


def test_get_alokasi_mengembalikan_hasil_akhir(client, pasar: Pasar, admin_headers):
    _siapkan_hasil(client, pasar, admin_headers)
    respons = client.get("/api/alokasi", params={"periode_id": pasar.periode_id})

    assert respons.status_code == 200, respons.text
    isi = respons.json()
    assert isi["total"] == 3
    assert isi["page"] == 1
    assert len(isi["data"]) == 3
    baris = isi["data"][0]
    assert {"nim", "nama_mahasiswa", "nidn", "nama_dosen", "tahap", "status"} <= set(baris)
    assert all(b["status"] == "terkunci" for b in isi["data"])
    assert all(b["tahap"] == "utama" for b in isi["data"])


def test_get_alokasi_filter_dosen(client, pasar: Pasar, admin_headers):
    _siapkan_hasil(client, pasar, admin_headers)
    d1 = pasar.dosen_ids[0]
    isi = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "dosen_id": d1}
    ).json()

    assert isi["total"] == 2
    assert {b["dosen_id"] for b in isi["data"]} == {d1}


def test_get_alokasi_filter_mahasiswa(client, pasar: Pasar, admin_headers):
    _siapkan_hasil(client, pasar, admin_headers)
    m3 = pasar.mahasiswa_ids[2]
    isi = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "mahasiswa_id": m3}
    ).json()

    assert isi["total"] == 1
    assert isi["data"][0]["mahasiswa_id"] == m3
    assert isi["data"][0]["dosen_id"] == pasar.dosen_ids[1]


def test_get_alokasi_paginasi(client, pasar: Pasar, admin_headers):
    _siapkan_hasil(client, pasar, admin_headers)
    halaman1 = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "page": 1, "page_size": 2}
    ).json()
    halaman2 = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "page": 2, "page_size": 2}
    ).json()

    assert halaman1["total"] == halaman2["total"] == 3
    assert len(halaman1["data"]) == 2
    assert len(halaman2["data"]) == 1
    assert {b["id"] for b in halaman1["data"]}.isdisjoint({b["id"] for b in halaman2["data"]})


def test_get_alokasi_filter_tahap_susulan(client, pasar: Pasar, admin_headers):
    _siapkan_hasil(client, pasar, admin_headers)
    m4, d3 = pasar.mahasiswa_ids[3], pasar.dosen_ids[2]
    isi_preferensi(client, pasar, mahasiswa={m4: [d3]}, dosen={})
    eksekusi(client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "susulan"})

    isi = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "tahap": "susulan"}
    ).json()
    assert isi["total"] == 1
    assert isi["data"][0]["mahasiswa_id"] == m4

    semua = client.get("/api/alokasi", params={"periode_id": pasar.periode_id}).json()
    assert semua["total"] == 4


def test_get_alokasi_filter_status_tentatif(client, pasar: Pasar, admin_headers):
    m1, d1 = pasar.mahasiswa_ids[0], pasar.dosen_ids[0]
    isi_preferensi(client, pasar, mahasiswa={m1: [d1]}, dosen={d1: [m1]})
    eksekusi(
        client, admin_headers, {"periode_id": pasar.periode_id, "tahap": "utama", "kunci": False}
    )

    assert client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "status": "tentatif"}
    ).json()["total"] == 1
    assert client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "status": "terkunci"}
    ).json()["total"] == 0


def test_get_alokasi_periode_tak_dikenal_404(client):
    respons = client.get("/api/alokasi", params={"periode_id": 9999})
    assert respons.status_code == 404


def test_get_alokasi_tanpa_periode_id_422(client):
    assert client.get("/api/alokasi").status_code == 422


def test_get_alokasi_page_size_di_atas_batas_422(client, pasar: Pasar):
    respons = client.get(
        "/api/alokasi", params={"periode_id": pasar.periode_id, "page_size": 500}
    )
    assert respons.status_code == 422


def test_get_alokasi_kosong_sebelum_matching(client, pasar: Pasar):
    isi = client.get("/api/alokasi", params={"periode_id": pasar.periode_id}).json()
    assert isi["total"] == 0
    assert isi["data"] == []