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
