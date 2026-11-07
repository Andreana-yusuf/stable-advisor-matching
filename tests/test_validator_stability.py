"""Menguji validator itu sendiri: harus bisa mendeteksi matching yang buruk."""

from __future__ import annotations

from app.algorithms import (
    find_blocking_pairs,
    find_quota_violations,
    find_rationality_violations,
    gale_shapley,
    verify_matching,
)

MAHASISWA = {"m1": ["d1", "d2"], "m2": ["d1", "d2"], "m3": ["d2", "d1"]}
DOSEN = {"d1": ["m2", "m1", "m3"], "d2": ["m1", "m2", "m3"]}
KUOTA = {"d1": 1, "d2": 1}


def test_validator_mendeteksi_blocking_pair_kuota_tersisa():
    # m2 seharusnya dapat d1 (prioritas utama d1), tapi d1 dibiarkan kosong.
    cacat = {"m1": "d2"}
    blocks = find_blocking_pairs(cacat, MAHASISWA, DOSEN, KUOTA)

    assert {(b.student_id, b.lecturer_id, b.reason) for b in blocks} >= {
        ("m2", "d1", "kuota_tersisa")
    }


def test_validator_mendeteksi_blocking_pair_yang_menggusur():
    # d1 dipegang m1 padahal d1 lebih memilih m2, dan m2 juga memilih d1.
    cacat = {"m1": "d1", "m2": "d2"}
    blocks = find_blocking_pairs(cacat, MAHASISWA, DOSEN, KUOTA)

    assert any(
        b.student_id == "m2"
        and b.lecturer_id == "d1"
        and b.reason == "menggusur_penerima_terburuk"
        and b.displaced_student_id == "m1"
        for b in blocks
    )
    assert not verify_matching(cacat, MAHASISWA, DOSEN, KUOTA).is_stable


def test_validator_melaporkan_pelanggaran_kuota():
    cacat = {"m1": "d1", "m2": "d1"}
    pelanggaran = find_quota_violations(cacat, KUOTA)

    assert len(pelanggaran) == 1
    assert pelanggaran[0].lecturer_id == "d1"
    assert (pelanggaran[0].assigned, pelanggaran[0].quota) == (2, 1)


def test_validator_menolak_dosen_tanpa_kuota():
    pelanggaran = find_quota_violations({"m1": "d9"}, KUOTA)
    assert pelanggaran[0].lecturer_id == "d9"
    assert pelanggaran[0].quota == 0


def test_validator_mendeteksi_pasangan_tidak_saling_menerima():
    rasionalitas = find_rationality_violations({"m3": "d1"}, MAHASISWA, DOSEN, KUOTA)
    assert rasionalitas == ()  # m3 memang mencantumkan d1 dan d1 menerima m3

    tidak_acceptable = find_rationality_violations(
        {"m4": "d1"}, {"m4": ["d1"]}, {"d1": ["m1"]}, {"d1": 2}
    )
    assert tidak_acceptable[0].reason == "mahasiswa tidak diterima dosen"

    pilihan_salah = find_rationality_violations(
        {"m1": "d9"}, {"m1": ["d1"]}, {"d9": ["m1"]}, {"d9": 1}
    )
    assert pilihan_salah[0].reason == "dosen tidak ada di preferensi mahasiswa"


def test_matching_stabil_tidak_menghasilkan_pelanggaran():
    hasil = gale_shapley(MAHASISWA, DOSEN, KUOTA)
    laporan = verify_matching(hasil.student_to_lecturer, MAHASISWA, DOSEN, KUOTA)

    assert laporan.blocking_pairs == ()
    assert laporan.quota_violations == ()
    assert laporan.rationality_violations == ()
    assert laporan.is_stable and laporan.is_valid


def test_mahasiswa_terkunci_dikecualikan_dari_analisis_blocking_pair():
    # m1 dikunci di d2 padahal d1 (pilihan utamanya) masih kosong.
    matching = {"m1": "d2"}
    tanpa_pembekuan = find_blocking_pairs(matching, MAHASISWA, DOSEN, KUOTA)
    dengan_pembekuan = find_blocking_pairs(
        matching, MAHASISWA, DOSEN, KUOTA, mahasiswa_terkunci=["m1"]
    )

    assert any(b.student_id == "m1" for b in tanpa_pembekuan)
    assert all(b.student_id != "m1" for b in dengan_pembekuan)