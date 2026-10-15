import json
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from openpyxl import Workbook

from apps.core.registry import get_spec
from apps.imports.engine import (
    MappingConfig,
    check_mapping,
    run_dry_run,
)
from apps.imports.readers import Table
from apps.referensi.models import AliasKabKota
from apps.sekolah.models import Sekolah

pytestmark = pytest.mark.django_db


def test_check_mapping_kolom_tidak_ada_di_file():
    spec = get_spec("sekolah")
    mapping = MappingConfig(columns={"TidakAda": "npsn"})
    errors = check_mapping(spec, mapping, available_headers=["NPSN", "Nama"])
    assert any("tidak ditemukan" in err for err in errors)


def test_check_mapping_field_dipetakan_lebih_dari_sekali():
    spec = get_spec("sekolah")
    mapping = MappingConfig(columns={"Kolom1": "npsn", "Kolom2": "npsn"})
    errors = check_mapping(spec, mapping, available_headers=["Kolom1", "Kolom2"])
    assert any("lebih dari satu kali" in err for err in errors)


def test_check_mapping_field_wajib_belum_dipetakan():
    spec = get_spec("sekolah")
    mapping = MappingConfig(columns={"NPSN": "npsn"})
    errors = check_mapping(spec, mapping, available_headers=["NPSN"])
    assert any("nama" in err for err in errors)


def test_check_mapping_menolak_field_tujuan_yang_tidak_dikenal():
    spec = get_spec("sekolah")
    mapping = MappingConfig(columns={"NPSN": "npsn", "Nama": "kolom_rahasia"})
    errors = check_mapping(spec, mapping, available_headers=["NPSN", "Nama"])
    assert any("tidak dapat dipetakan" in err for err in errors)


def test_check_mapping_menolak_field_sistem():
    spec = get_spec("sekolah")
    mapping = MappingConfig(columns={"Tanggal dibuat": "created_at"})
    errors = check_mapping(spec, mapping, available_headers=["Tanggal dibuat"])
    assert any("created_at" in err and "tidak dapat dipetakan" in err for err in errors)


def test_admin_value_maps_override(wilayah):
    spec = get_spec("sekolah")
    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    rows = [
        headers,
        ["10100099", "SMP Uji", "Kota Bandung", "Negeri", "Custom Dinas", "Pelaksana"],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    # Tanpa value_maps, "Custom Dinas" tidak dikenali
    mapping_no_map = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )
    prev1 = run_dry_run(spec, table, mapping_no_map)
    assert prev1.counts()["error"] == 1
    assert "pengusul" in prev1.unknown_values
    assert "Custom Dinas" in prev1.unknown_values["pengusul"]

    # Dengan value_maps
    mapping_with_map = MappingConfig(
        columns=mapping_no_map.columns,
        value_maps={"pengusul": {"Custom Dinas": "dinas"}},
    )
    prev2 = run_dry_run(spec, table, mapping_with_map)
    assert prev2.counts()["error"] == 0
    assert prev2.rows[0].values["pengusul"] == "dinas"


def test_alias_kabkota_manual_mengoreksi_provinsi_yang_bertentangan(wilayah):
    spec = get_spec("sekolah")
    headers = [
        "NPSN",
        "Nama",
        "Provinsi",
        "Kab/Kota",
        "Status",
        "Pengusul",
        "Mapel KKA",
    ]
    rows = [
        headers,
        [
            "10100098",
            "SMP Malang",
            "Jawa Barat",
            "Kab. Malang",
            "Negeri",
            "Dinas Pendidikan",
            "Pelaksana",
        ],
    ]
    table = Table(name="Data", rows=rows, n_cols=len(headers))
    fields = ["npsn", "nama", "provinsi", "kabkota", "status", "pengusul", "mapel_kka"]
    columns = dict(zip(headers, fields, strict=True))
    mapping = MappingConfig(columns=columns)

    unresolved = run_dry_run(spec, table, mapping)
    assert unresolved.counts()["error"] == 1
    assert "Kab. Malang" in unresolved.unknown_values["kabkota"]

    mapping.value_maps = {"kabkota": {"Kab. Malang": "Kabupaten Malang"}}
    resolved = run_dry_run(spec, table, mapping)
    assert resolved.counts()["error"] == 0
    assert resolved.rows[0].values["kabkota"] == wilayah.malang
    assert resolved.rows[0].values["provinsi"] == wilayah.jatim
    assert any(issue.level == "warning" for issue in resolved.rows[0].issues)


def test_alias_kabkota_tersimpan_tetap_mengoreksi_provinsi(wilayah):
    AliasKabKota.objects.create(alias="Kab. Malang", kabkota=wilayah.malang)
    headers = ["NPSN", "Nama", "Provinsi", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    table = Table(
        name="Data",
        rows=[
            headers,
            [
                "10100097",
                "SMP Malang",
                "Jawa Barat",
                "Kab. Malang",
                "Negeri",
                "Dinas Pendidikan",
                "Pelaksana",
            ],
        ],
        n_cols=len(headers),
    )
    mapping = MappingConfig(
        columns=dict(
            zip(
                headers,
                ["npsn", "nama", "provinsi", "kabkota", "status", "pengusul", "mapel_kka"],
                strict=True,
            )
        )
    )

    preview = run_dry_run(get_spec("sekolah"), table, mapping)

    assert preview.counts()["error"] == 0
    assert preview.rows[0].values["kabkota"] == wilayah.malang
    assert preview.rows[0].values["provinsi"] == wilayah.jatim


def test_dry_run_tidak_menyimpan_perubahan(wilayah):
    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"]
    values = ["10100096", "SMP Uji", "Kota Bandung", "Negeri", "Dinas Pendidikan", "Pelaksana"]
    table = Table(name="Data", rows=[headers, values], n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )

    preview = run_dry_run(get_spec("sekolah"), table, mapping)

    assert preview.counts()["create"] == 1
    assert Sekolah.all_objects.count() == 0


def test_bar_isian_tidak_boleh_menimpa_bar_header():
    table = Table(name="Data", rows=[["NPSN"], ["10100001"]], n_cols=1)
    mapping = MappingConfig(
        columns={"NPSN": "npsn"},
        header_rows=(1,),
        first_data_row=1,
    )

    preview = run_dry_run(get_spec("sekolah"), table, mapping)

    assert not preview.ok
    assert any("setelah semua baris header" in error for error in preview.mapping_errors)


def test_jumlah_guru_negatif_ditolak(wilayah):
    headers = ["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA", "Jumlah Guru"]
    values = [
        "10100098",
        "SMP Uji",
        "Kota Bandung",
        "Negeri",
        "Dinas Pendidikan",
        "Pelaksana",
        "-1",
    ]
    table = Table(name="Data", rows=[headers, values], n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
            "Jumlah Guru": "jumlah_guru",
        }
    )

    preview = run_dry_run(get_spec("sekolah"), table, mapping)

    assert preview.counts()["error"] == 1
    assert any(issue.field == "jumlah_guru" for _, issue in preview.issues())


def test_provinsi_kosong_ditentukan_dari_kabkota_saat_memperbarui(wilayah, make_sekolah):
    existing = make_sekolah(npsn="10100097", provinsi=wilayah.jabar, kabkota=wilayah.bandung)
    headers = [
        "NPSN",
        "Nama",
        "Provinsi",
        "Kab/Kota",
        "Status",
        "Pengusul",
        "Mapel KKA",
    ]
    values = [
        existing.npsn,
        existing.nama,
        "",
        "Kabupaten Malang",
        "Negeri",
        "Dinas Pendidikan",
        "Pelaksana",
    ]
    table = Table(name="Data", rows=[headers, values], n_cols=len(headers))
    mapping = MappingConfig(
        columns={
            "NPSN": "npsn",
            "Nama": "nama",
            "Provinsi": "provinsi",
            "Kab/Kota": "kabkota",
            "Status": "status",
            "Pengusul": "pengusul",
            "Mapel KKA": "mapel_kka",
        }
    )

    preview = run_dry_run(get_spec("sekolah"), table, mapping)

    assert preview.counts()["error"] == 0
    assert preview.rows[0].action == "update"
    assert {name for name, _, _ in preview.rows[0].changes} >= {"provinsi", "kabkota"}


def test_management_command_import_dryrun_berhasil(wilayah):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Buat file xlsx
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"])
        ws.append(
            [
                "10100088",
                "SMP Uji Command",
                "Kota Bandung",
                "Negeri",
                "Dinas Pendidikan",
                "Pelaksana",
            ]
        )
        xlsx_file = tmp_path / "data.xlsx"
        wb.save(xlsx_file)

        # Buat file mapping
        mapping_data = {
            "columns": {
                "NPSN": "npsn",
                "Nama": "nama",
                "Kab/Kota": "kabkota",
                "Status": "status",
                "Pengusul": "pengusul",
                "Mapel KKA": "mapel_kka",
            }
        }
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps(mapping_data), encoding="utf-8")

        out = StringIO()
        call_command(
            "import_dryrun",
            "sekolah",
            str(xlsx_file),
            mapping=str(mapping_file),
            stdout=out,
        )
        output = out.getvalue()
        assert "Hasil dry-run: 1 baru, 0 perbarui, 0 tanpa perubahan, 0 error." in output


def test_management_command_import_dryrun_error_baris(wilayah):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["NPSN", "Nama", "Kab/Kota", "Status", "Pengusul", "Mapel KKA"])
        ws.append(
            [
                "123",
                "SMP Error NPSN",
                "Kota Bandung",
                "Negeri",
                "Dinas Pendidikan",
                "Pelaksana",
            ]
        )
        xlsx_file = tmp_path / "data.xlsx"
        wb.save(xlsx_file)

        mapping_data = {
            "columns": {
                "NPSN": "npsn",
                "Nama": "nama",
                "Kab/Kota": "kabkota",
                "Status": "status",
                "Pengusul": "pengusul",
                "Mapel KKA": "mapel_kka",
            }
        }
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps(mapping_data), encoding="utf-8")

        out = StringIO()
        with pytest.raises(CommandError, match="1 baris mengalami error"):
            call_command(
                "import_dryrun",
                "sekolah",
                str(xlsx_file),
                mapping=str(mapping_file),
                stdout=out,
            )


def test_management_command_dataset_tidak_ada():
    with pytest.raises(CommandError, match="tidak ditemukan"):
        call_command("import_dryrun", "tidak_ada", "file.xlsx", mapping="map.json")


def test_management_command_csv_meminta_encoding_dan_pemisah_dipilih():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("NPSN;Nama\n", encoding="utf-8")
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps({"columns": {}}), encoding="utf-8")

        with pytest.raises(CommandError, match="pilih --encoding dan --delimiter"):
            call_command(
                "import_dryrun",
                "sekolah",
                str(csv_file),
                mapping=str(mapping_file),
            )


def test_management_command_menolak_mapping_json_bukan_objek():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_file = tmp_path / "data.csv"
        data_file.write_text("NPSN;Nama\n", encoding="utf-8")
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text("[]", encoding="utf-8")

        with pytest.raises(CommandError, match="objek JSON"):
            call_command(
                "import_dryrun",
                "sekolah",
                str(data_file),
                mapping=str(mapping_file),
            )
