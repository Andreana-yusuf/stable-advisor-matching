"""Mekanisme susulan: late-register tidak boleh merusak alokasi yang terkunci."""

from __future__ import annotations

import pytest

from app.algorithms import (
    UnrankedPolicy,
    gale_shapley,
    match_late_registrants,
    residual_capacity,
    verify_matching,
)

DOSEN = {"d1": ["m1", "m2", "m3"], "d2": ["m2", "m1"]}
KUOTA = {"d1": 2, "d2": 1}


def test_susulan_mempertahankan_alokasi_terkunci():
    terkunci = {"m1": "d1", "m2": "d2"}
    late = {"m3": ["d1", "d2"], "m4": ["d2", "d1"]}

    hasil = match_late_registrants(late, DOSEN, KUOTA, terkunci)

    assert hasil.locked == terkunci
    assert {a.student_id: a.lecturer_id for a in hasil.newly_assigned} == {"m3": "d1"}
    assert hasil.unmatched == ("m4",)
    assert all(a.round_number == 0 for a in hasil.assignments if a.is_locked)


def test_susulan_hanya_memakai_sisa_kuota():
    terkunci = {"m1": "d1", "m2": "d1", "m3": "d2"}
    late = {"m4": ["d1", "d2"], "m5": ["d2", "d1"]}

    hasil = match_late_registrants(late, DOSEN, KUOTA, terkunci)

    assert hasil.newly_assigned == ()
    assert set(hasil.unmatched) == {"m4", "m5"}
    assert hasil.proposal_count == 0


def test_susulan_total_tetap_patuh_kuota():
    terkunci = {"m1": "d1"}
    late = {"m2": ["d1", "d2"], "m3": ["d1", "d2"], "m4": ["d2", "d1"]}

    hasil = match_late_registrants(late, DOSEN, KUOTA, terkunci)

    for dosen_id, penerima in hasil.lecturer_to_students.items():
        assert len(penerima) <= KUOTA[dosen_id], f"kuota {dosen_id} terlampaui"
    assert hasil.locked == terkunci


def test_susulan_stabil_pada_pasar_residual():
    terkunci = {"m2": "d2"}
    late = {"m3": ["d2", "d1"], "m4": ["d1"], "m1": ["d1", "d2"]}
    urutan = tuple(late)

    hasil = match_late_registrants(late, DOSEN, KUOTA, terkunci, urutan_pengusul=urutan)
    baru = {a.student_id: a.lecturer_id for a in hasil.newly_assigned}
    laporan = verify_matching(
        baru,
        late,
        DOSEN,
        residual_capacity(KUOTA, terkunci),
        kebijakan_tak_terperingkat=UnrankedPolicy.APPEND,
        urutan_pengusul=urutan,
    )

    assert laporan.is_stable, laporan


def test_late_register_lebih_prioritas_tidak_menggusur_yang_terkunci():
    dosen = {"d1": ["m9", "m1"]}
    terkunci = {"m1": "d1"}
    late = {"m9": ["d1"]}

    hasil = match_late_registrants(late, dosen, {"d1": 1}, terkunci)

    assert hasil.locked == terkunci
    assert hasil.newly_assigned == ()
    assert hasil.unmatched == ("m9",)


def test_append_menerima_late_register_yang_belum_diranking_dosen():
    late = {"m9": ["d1"]}
    ketat = match_late_registrants(
        late, DOSEN, {"d1": 1, "d2": 1}, {}, kebijakan_tak_terperingkat=UnrankedPolicy.REJECT
    )
    longgar = match_late_registrants(
        late, DOSEN, {"d1": 1, "d2": 1}, {}, kebijakan_tak_terperingkat=UnrankedPolicy.APPEND
    )

    assert ketat.unmatched == ("m9",)
    assert longgar.student_to_lecturer == {"m9": "d1"}
    assert longgar.assignments[0].lecturer_rank is None


def test_susulan_tanpa_kunci_setara_dengan_utama():
    mahasiswa = {"m1": ["d1", "d2"], "m2": ["d2", "d1"]}
    utama = gale_shapley(
        mahasiswa, DOSEN, KUOTA, kebijakan_tak_terperingkat=UnrankedPolicy.APPEND
    )
    susulan = match_late_registrants(mahasiswa, DOSEN, KUOTA, {})

    assert susulan.student_to_lecturer == utama.student_to_lecturer
    assert susulan.locked == {}


def test_susulan_berulang_tetap_stabil_dan_kumulatif():
    terkunci: dict[str, str] = {}
    gelombang = [
        {"m1": ["d1", "d2"]},
        {"m2": ["d2", "d1"], "m3": ["d1", "d2"]},
        {"m4": ["d1", "d2"]},
    ]
    for late in gelombang:
        hasil = match_late_registrants(late, DOSEN, KUOTA, terkunci)
        assert hasil.locked == terkunci
        baru = {a.student_id: a.lecturer_id for a in hasil.newly_assigned}
        laporan = verify_matching(
            baru,
            late,
            DOSEN,
            residual_capacity(KUOTA, terkunci),
            kebijakan_tak_terperingkat=UnrankedPolicy.APPEND,
            urutan_pengusul=tuple(late),
        )
        assert laporan.is_stable, laporan
        terkunci = hasil.student_to_lecturer
        for dosen_id, penerima in hasil.lecturer_to_students.items():
            assert len(penerima) <= KUOTA[dosen_id]

    assert len(terkunci) == 3  # total kuota 3, gelombang terakhir kehabisan kursi


def test_peserta_susulan_yang_sudah_terkunci_ditolak():
    with pytest.raises(ValueError, match="sudah terkunci"):
        match_late_registrants({"m1": ["d1"]}, DOSEN, KUOTA, {"m1": "d1"})


def test_kunci_melebihi_kuota_ditolak():
    with pytest.raises(ValueError, match="melampaui kuota"):
        match_late_registrants({"m3": ["d1"]}, DOSEN, {"d1": 1}, {"m1": "d1", "m2": "d1"})


def test_kunci_ke_dosen_tak_dikenal_ditolak():
    with pytest.raises(ValueError, match="tak dikenal"):
        match_late_registrants({"m3": ["d1"]}, DOSEN, KUOTA, {"m1": "d9"})


def test_urutan_pengusul_susulan_deterministik():
    late = {"m4": ["d1"], "m9": ["d1"]}
    dosen = {"d1": []}
    pertama = match_late_registrants(
        late, dosen, {"d1": 1}, {}, urutan_pengusul=("m4", "m9")
    )
    kedua = match_late_registrants(
        late, dosen, {"d1": 1}, {}, urutan_pengusul=("m9", "m4")
    )

    # Keduanya sah (append mengikuti urutan kedatangan), tapi harus reproducible.
    assert pertama.student_to_lecturer == {"m4": "d1"}
    assert kedua.student_to_lecturer == {"m9": "d1"}
    assert match_late_registrants(
        late, dosen, {"d1": 1}, {}, urutan_pengusul=("m4", "m9")
    ).student_to_lecturer == pertama.student_to_lecturer