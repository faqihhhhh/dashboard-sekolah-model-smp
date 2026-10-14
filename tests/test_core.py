import csv
import json
from pathlib import Path

import pytest
from django.urls import reverse

from apps.accounts.models import Role


def test_geojson_peta_memuat_38_provinsi_dengan_kode_kemendagri():
    data_path = Path(__file__).resolve().parents[1] / "static/data/indonesia-38-provinces.geojson"
    geojson = json.loads(data_path.read_text(encoding="utf-8"))
    features = geojson["features"]
    papua_codes = {
        "Papua Selatan": "93",
        "Papua Tengah": "94",
        "Papua Pegunungan": "95",
        "Papua Barat Daya": "96",
    }
    map_codes = {
        papua_codes.get(feature["properties"]["PROVINSI"], feature["properties"]["KODE_PROV"])
        for feature in features
    }
    csv_path = Path(__file__).resolve().parents[1] / "apps/referensi/data/wilayah.csv"
    with csv_path.open(encoding="utf-8", newline="") as source:
        official_codes = {row["kode"] for row in csv.DictReader(source) if "." not in row["kode"]}

    assert len(features) == 38
    assert len({feature["properties"]["PROVINSI"] for feature in features}) == 38
    assert map_codes == official_codes


@pytest.mark.django_db
def test_healthz_ok(client):
    response = client.get(reverse("core:healthz"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
@pytest.mark.parametrize("role", [None, Role.VIEWER, Role.ADMIN, Role.SUPER_ADMIN])
def test_home_menampilkan_ringkasan_publik_per_peran(client, client_as, make_sekolah, role):
    make_sekolah(status="negeri", pengusul="dinas", mapel_kka="pelaksana")
    make_sekolah(status="swasta", pengusul="mitra", mapel_kka="bukan")

    current_client = client_as(role) if role else client
    response = current_client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b"Dasbor Program Sekolah Model SMP" in response.content
    assert response.context["totals"] == {
        "total": 2,
        "negeri": 1,
        "swasta": 1,
        "dinas": 1,
        "mitra": 1,
        "kka": 1,
    }
    assert [(item.nama, item.total) for item in response.context["provinsi"]] == [
        ("Jawa Barat", 2),
        ("Jawa Timur", 0),
    ]
    assert b"jumlah guru" not in response.content.lower()


@pytest.mark.django_db
def test_filter_beranda_diterapkan_konsisten_ke_kpi_dan_provinsi(client, make_sekolah, wilayah):
    make_sekolah(status="negeri", pengusul="dinas", mapel_kka="pelaksana")
    make_sekolah(
        status="swasta",
        pengusul="mitra",
        mapel_kka="bukan",
        provinsi=wilayah.jatim,
        kabkota=wilayah.malang,
    )

    response = client.get(
        reverse("core:home"),
        {"provinsi": "35", "status": "swasta", "pengusul": "mitra", "mapel_kka": "bukan"},
    )

    assert response.status_code == 200
    assert response.context["totals"]["total"] == 1
    assert response.context["totals"]["dinas"] == 0
    assert response.context["totals"]["mitra"] == 1
    assert [(item.nama, item.total) for item in response.context["provinsi"]] == [
        ("Jawa Barat", 0),
        ("Jawa Timur", 1),
    ]


@pytest.mark.django_db
def test_endpoint_agregat_publik_tidak_mengirim_data_sekolah(client, make_sekolah):
    school = make_sekolah(nama="SMP Data Privat")

    response = client.get(reverse("core:home_aggregate"))

    assert response.status_code == 200
    assert response.json()["totals"]["total"] == 1
    assert response.json()["provinsi"][0]["nama"] == "Jawa Barat"
    assert school.nama.encode() not in response.content
    assert school.npsn.encode() not in response.content
    assert b"jumlah_guru" not in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("role", [None, Role.VIEWER, Role.ADMIN, Role.SUPER_ADMIN])
def test_surat_dukungan_menunjukkan_status_belum_tersedia(client, client_as, role):
    current_client = client_as(role) if role else client
    response = current_client.get(reverse("core:surat_dukungan"))

    assert response.status_code == 200
    assert b"Surat Dukungan" in response.content
    assert b"Data surat belum tersedia" in response.content
    assert b"Belum Unggah" not in response.content
