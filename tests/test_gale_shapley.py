from __future__ import annotations

import random

import pytest

from app.algorithms import (
    UnrankedPolicy,
    gale_shapley,
    residual_capacity,
    verify_matching,
)
from tests.referens_bruteforce import pilihan_terbaik_student_optimal, semua_matching_stabil


def test_kasus_klasik_dua_sisi():
    mahasiswa = {"m1": ["d1", "d2"], "m2": ["d1", "d2"], "m3": ["d2", "d1"]}
    dosen = {"d1": ["m2", "m1", "m3"], "d2": ["m1", "m2", "m3"]}
    kuota = {"d1": 1, "d2": 1}

    hasil = gale_shapley(mahasiswa, dosen, kuota)

    assert hasil.student_to_lecturer == {"m1": "d2", "m2": "d1"}
    assert hasil.unmatched == ("m3",)
    assert hasil.proposal_count == 5
    assert verify_matching(hasil.student_to_lecturer, mahasiswa, dosen, kuota).is_stable


def test_dosen_menggusur_penerima_yang_lebih_buruk():
    mahasiswa = {"m1": ["d1"], "m2": ["d1"]}
    dosen = {"d1": ["m2", "m1"]}
    hasil = gale_shapley(mahasiswa, dosen, {"d1": 1})

    assert hasil.student_to_lecturer == {"m2": "d1"}
    assert hasil.unmatched == ("m1",)
    assert any(r.reason.value == "kalah_peringkat" for r in hasil.rejections)


def test_kuota_banyak_diterima_semua():
    mahasiswa = {f"m{i}": ["d1"] for i in range(1, 6)}
    dosen = {"d1": [f"m{i}" for i in range(5, 0, -1)]}
    hasil = gale_shapley(mahasiswa, dosen, {"d1": 3})

    assert hasil.student_to_lecturer == {"m5": "d1", "m4": "d1", "m3": "d1"}
    assert set(hasil.unmatched) == {"m1", "m2"}
    assert len(hasil.lecturer_to_students["d1"]) == 3


def test_mahasiswa_tanpa_pilihan_yang_acceptable_tidak_teralokasi():
    mahasiswa = {"m1": ["d1"]}
    dosen = {"d1": ["m2"]}
    hasil = gale_shapley(mahasiswa, dosen, {"d1": 5})

    assert hasil.student_to_lecturer == {}
    assert hasil.unmatched == ("m1",)
    assert hasil.rejections[0].reason.value == "tidak_acceptable"


def test_kebijakan_append_menerima_yang_tak_terperingkat():
    mahasiswa = {"m1": ["d1"]}
    dosen = {"d1": []}
    ketat = gale_shapley(mahasiswa, dosen, {"d1": 1})
    longgar = gale_shapley(
        mahasiswa, dosen, {"d1": 1}, kebijakan_tak_terperingkat=UnrankedPolicy.APPEND
    )

    assert ketat.unmatched == ("m1",)
    assert longgar.student_to_lecturer == {"m1": "d1"}
    assert longgar.assignments[0].lecturer_rank is None


def test_urutan_pengusul_tidak_memengaruhi_hasil():
    mahasiswa = {"m1": ["d1", "d2"], "m2": ["d2", "d1"], "m3": ["d1", "d2"]}
    dosen = {"d1": ["m3", "m2", "m1"], "d2": ["m1", "m3", "m2"]}
    kuota = {"d1": 1, "d2": 2}
    acuan = gale_shapley(mahasiswa, dosen, kuota).student_to_lecturer

    for urutan in (["m3", "m1", "m2"], ["m2", "m3", "m1"], ["m1", "m2", "m3"]):
        assert gale_shapley(mahasiswa, dosen, kuota, urutan_pengusul=urutan).student_to_lecturer == acuan


def test_hasil_bersifat_student_optimal_dibanding_brute_force():
    mahasiswa = {
        "m1": ["d1", "d2", "d3"],
        "m2": ["d2", "d1", "d3"],
        "m3": ["d1", "d2", "d3"],
    }
    dosen = {
        "d1": ["m2", "m1", "m3"],
        "d2": ["m1", "m2", "m3"],
        "d3": ["m1", "m2", "m3"],
    }
    kuota = {"d1": 1, "d2": 1, "d3": 1}

    stabil = semua_matching_stabil(mahasiswa, dosen, kuota)
    assert len(stabil) >= 2, "pasar harus punya lebih dari satu matching stabil agar uji bermakna"
    optimal = pilihan_terbaik_student_optimal(stabil, mahasiswa)
    hasil = gale_shapley(mahasiswa, dosen, kuota).student_to_lecturer

    assert hasil == {s: d for s, d in optimal.items() if d is not None}


def test_input_kosong_menghasilkan_hasil_kosong():
    hasil = gale_shapley({}, {}, {})
    assert hasil.assignments == ()
    assert hasil.unmatched == ()
    assert hasil.rounds == 0
    assert hasil.proposal_count == 0


def test_preferensi_duplikat_ditolak():
    with pytest.raises(ValueError, match="lebih dari sekali"):
        gale_shapley({"m1": ["d1", "d1"]}, {"d1": ["m1"]}, {"d1": 1})
    with pytest.raises(ValueError, match="lebih dari sekali"):
        gale_shapley({"m1": ["d1"]}, {"d1": ["m1", "m1"]}, {"d1": 1})


def test_kuota_negatif_ditolak():
    with pytest.raises(ValueError, match="negatif"):
        gale_shapley({"m1": ["d1"]}, {"d1": ["m1"]}, {"d1": -1})


def test_dosen_tak_dikenal_dalam_preferensi_ditolak():
    with pytest.raises(ValueError, match="tak dikenal"):
        gale_shapley({"m1": ["d9"]}, {}, {"d1": 1})


def test_dosen_berkuota_nol_diabaikan_tanpa_membuang_proposal():
    mahasiswa = {"m1": ["d1", "d2"]}
    dosen = {"d1": ["m1"], "d2": ["m1"]}
    hasil = gale_shapley(mahasiswa, dosen, {"d1": 0, "d2": 1})

    assert hasil.student_to_lecturer == {"m1": "d2"}
    assert hasil.proposal_count == 1


def test_residual_capacity_mengurangi_kursi_terkunci():
    assert residual_capacity({"d1": 3, "d2": 1}, {"m1": "d1", "m2": "d1"}) == {"d1": 1, "d2": 1}


def test_residual_capacity_menolak_kunci_melebihi_kuota():
    with pytest.raises(ValueError, match="melampaui kuota"):
        residual_capacity({"d1": 1}, {"m1": "d1", "m2": "d1"})


def test_pasar_acak_selalu_stabil_dan_patuh_kuota():
    rng = random.Random(20261107)
    for _ in range(250):
        jumlah_mhs = rng.randint(1, 8)
        jumlah_dosen = rng.randint(1, 4)
        mahasiswa_ids = [f"m{i}" for i in range(jumlah_mhs)]
        dosen_ids = [f"d{i}" for i in range(jumlah_dosen)]
        kuota = {d: rng.randint(0, 3) for d in dosen_ids}
        mahasiswa = {
            m: rng.sample(dosen_ids, rng.randint(0, jumlah_dosen)) for m in mahasiswa_ids
        }
        dosen = {d: rng.sample(mahasiswa_ids, rng.randint(0, jumlah_mhs)) for d in dosen_ids}
        mahasiswa = {m: v for m, v in mahasiswa.items() if v}
        if not mahasiswa:
            continue

        hasil = gale_shapley(mahasiswa, dosen, kuota)
        laporan = verify_matching(hasil.student_to_lecturer, mahasiswa, dosen, kuota)

        assert laporan.is_stable, f"pasar tidak stabil: {laporan}"
        for dosen_id, penerima in hasil.lecturer_to_students.items():
            assert len(penerima) <= kuota[dosen_id]
        assert set(hasil.student_to_lecturer) | set(hasil.unmatched) == set(mahasiswa)