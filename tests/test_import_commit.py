"""Tes alur dry-run -> commit pada dataset Sekolah (butuh database).

Memakai fixture wilayah, make_sekolah, dan make_user dari tests/conftest.py.
Wilayah uji: Kota Bandung dan Kabupaten Bogor (Jawa Barat), Kabupaten Malang (Jawa Timur).
"""

import pytest

from apps.accounts.models import Role
from apps.core.registry import get_spec
from apps.imports.commit import CommitBlocked, commit_preview
from apps.imports.engine import MappingConfig, run_dry_run
from apps.imports.readers import Table
from apps.sekolah.models import Sekolah

HEADER = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA", "Jumlah Guru"]
COLUMNS = {
    "NPSN": "npsn",
    "Nama": "nama",
    "Kab/Kota": "kabkota",
    "Status": "status",
    "Pengusul": "pengusul",
    "Mapel KKA": "mapel_kka",
    "Jumlah Guru": "jumlah_guru",
}
pytestmark = pytest.mark.django_db


def make_table(*rows):
    all_rows = [HEADER, *rows]
    return Table(name="Data", rows=[list(r) for r in all_rows], n_cols=len(HEADER))


def mapping(**overrides):
    return MappingConfig(columns=overrides.get("columns", dict(COLUMNS)))


def dry_run(*rows, **overrides):
    return run_dry_run(get_spec("sekolah"), make_table(*rows), mapping(**overrides))


def baris(npsn, nama="SMP Impor", kab="Kota Bandung", status="Negeri", pengusul="Dinas Pendidikan",
          mapel="Pelaksana", guru="30"):  # fmt: skip
    return [npsn, nama, kab, status, pengusul, mapel, guru]


def spec():
    return get_spec("sekolah")


# --- Data baru ---


def test_impor_baru_menurunkan_provinsi_memakai_alias_dan_mencatat_riwayat(wilayah, make_user):
    admin = make_user(Role.ADMIN)
    preview = dry_run(baris("10100001", pengusul="Pemda"))  # "Pemda" = alias bawaan -> dinas
    assert preview.counts()["create"] == 1 and preview.counts()["error"] == 0

    result = commit_preview(spec(), preview, admin, reason="Impor: data.xlsx")
    assert (result.created, result.updated, result.skipped) == (1, 0, 0)

    sekolah = Sekolah.objects.get(npsn="10100001")
    assert sekolah.pengusul == "dinas"
    assert sekolah.provinsi == wilayah.jabar  # diturunkan dari kabupaten/kota
    record = sekolah.history.get()
    assert record.history_user == admin
    assert record.history_change_reason == "Impor: data.xlsx"


def test_dry_run_tidak_menulis_apa_pun(wilayah):
    dry_run(baris("10100001"), baris("10100002"))
    assert Sekolah.all_objects.count() == 0


# --- Campuran baru / perbarui / tanpa perubahan ---


def test_campuran_baru_perbarui_dan_tanpa_perubahan(wilayah, make_sekolah, make_user):
    make_sekolah(npsn="10100002", nama="Lama", jumlah_guru=10)
    make_sekolah(npsn="10100003", nama="Sama", jumlah_guru=5)
    preview = dry_run(
        baris("10100001", nama="Baru"),
        baris("10100002", nama="Diperbarui", guru="11"),
        baris("10100003", nama="Sama", guru="5"),
    )
    counts = preview.counts()
    assert [counts[k] for k in ("create", "update", "unchanged", "error")] == [1, 1, 1, 0]

    result = commit_preview(spec(), preview, make_user(Role.ADMIN))
    assert (result.created, result.updated, result.unchanged) == (1, 1, 1)

    updated = Sekolah.objects.get(npsn="10100002")
    assert (updated.nama, updated.jumlah_guru) == ("Diperbarui", 11)
    assert updated.history.count() == 2  # dibuat + diubah
    assert Sekolah.objects.get(npsn="10100003").history.count() == 1  # tidak disentuh


def test_sel_kosong_dan_na_tidak_menimpa_nilai_lama(wilayah, make_sekolah, make_user):
    make_sekolah(npsn="10100002", nama="Sama", jumlah_guru=10)
    preview = dry_run(baris("10100002", nama="Sama", guru="#N/A"))
    assert preview.counts()["unchanged"] == 1
    commit_preview(spec(), preview, make_user(Role.ADMIN))
    assert Sekolah.objects.get(npsn="10100002").jumlah_guru == 10


def test_perubahan_orang_lain_setelah_dry_run_tidak_tertimpa(wilayah, make_sekolah, make_user):
    sekolah = make_sekolah(npsn="10100002", nama="Lama", status="negeri")
    preview = dry_run(baris("10100002", nama="Dari Impor", guru="99"))
    # Admin lain mengubah status setelah dry-run (kolom Status pada file tidak berubah: "Negeri").
    Sekolah.objects.filter(pk=sekolah.pk).update(status="swasta")

    commit_preview(spec(), preview, make_user(Role.ADMIN))
    sekolah.refresh_from_db()
    assert sekolah.nama == "Dari Impor" and sekolah.jumlah_guru == 99
    assert sekolah.status == "swasta"  # perubahan orang lain tetap


def test_data_terhapus_sejak_dry_run_dilaporkan(wilayah, make_sekolah, make_user):
    sekolah = make_sekolah(npsn="10100002", nama="Lama")
    preview = dry_run(baris("10100002", nama="Baru"))
    sekolah.soft_delete()
    with pytest.raises(CommitBlocked, match="dihapus"):
        commit_preview(spec(), preview, make_user(Role.ADMIN))


# --- Error ---


def test_baris_error_memblokir_commit_dan_tidak_menyimpan_apa_pun(wilayah, make_user):
    preview = dry_run(baris("10100001"), baris("10100002", status="Entah"))
    assert preview.counts()["error"] == 1
    with pytest.raises(CommitBlocked, match="1 baris masih error"):
        commit_preview(spec(), preview, make_user(Role.ADMIN))
    assert Sekolah.all_objects.count() == 0


def test_skip_errors_menyimpan_yang_valid_saja(wilayah, make_user):
    preview = dry_run(baris("10100001"), baris("10100002", status="Entah"))
    result = commit_preview(spec(), preview, make_user(Role.ADMIN), skip_errors=True)
    assert (result.created, result.skipped) == (1, 1)
    assert list(Sekolah.objects.values_list("npsn", flat=True)) == ["10100001"]


def test_npsn_ganda_dalam_file_menjadi_error(wilayah):
    preview = dry_run(baris("10100001"), baris("10100001", nama="Kembar"))
    assert preview.counts()["error"] == 1
    assert any("Duplikat dalam file" in issue.message for _, issue in preview.issues())


def test_npsn_milik_data_terhapus_menjadi_error(wilayah, make_sekolah):
    make_sekolah(npsn="10100001").soft_delete()
    preview = dry_run(baris("10100001"))
    assert preview.counts()["error"] == 1
    assert any("telah dihapus" in issue.message for _, issue in preview.issues())


def test_npsn_bukan_8_digit_menjadi_error(wilayah):
    assert dry_run(baris("123")).counts()["error"] == 1


def test_kabkota_di_luar_provinsi_yang_dipetakan_menjadi_error(wilayah):
    columns = dict(COLUMNS) | {"Provinsi": "provinsi"}
    header = [*HEADER, "Provinsi"]
    table = Table(
        name="Data",
        rows=[header, [*baris("10100001", kab="Kabupaten Malang"), "Jawa Barat"]],
        n_cols=len(header),
    )
    preview = run_dry_run(spec(), table, MappingConfig(columns=columns))
    assert preview.counts()["error"] == 1


def test_pemetaan_tanpa_field_wajib_tidak_bisa_dicommit(wilayah, make_user):
    columns = {k: v for k, v in COLUMNS.items() if v != "npsn"}
    preview = dry_run(baris("10100001"), columns=columns)
    assert not preview.ok
    with pytest.raises(CommitBlocked, match="Pemetaan"):
        commit_preview(spec(), preview, make_user(Role.ADMIN))


def test_pengguna_anonim_tercatat_sebagai_sistem(wilayah):
    commit_preview(spec(), dry_run(baris("10100001")), None)
    assert Sekolah.objects.get().history.get().history_user is None
