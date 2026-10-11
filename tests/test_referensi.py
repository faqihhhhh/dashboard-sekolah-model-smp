from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.accounts.models import Role
from apps.referensi.management.commands.seed_wilayah import DEFAULT_CSV
from apps.referensi.models import (
    AliasKabKota,
    AliasProvinsi,
    JenisKabKota,
    KabKota,
    Periode,
    Provinsi,
)


@pytest.fixture
def mini_csv(tmp_path):
    path = tmp_path / "wilayah.csv"
    path.write_text(
        "kode,nama\n"
        "31,Daerah Khusus Ibukota Jakarta\n"
        "31.71,Kota Administrasi Jakarta Pusat\n"
        "32,Jawa Barat\n"
        "32.01,Kabupaten Bogor\n"
        "32.73,Kota Bandung\n",
        encoding="utf-8",
    )
    return path


# --- Seed wilayah ---


@pytest.mark.django_db
def test_seed_membuat_provinsi_kabkota_dan_alias(mini_csv):
    call_command("seed_wilayah", file=str(mini_csv))
    assert Provinsi.objects.count() == 2
    assert KabKota.objects.count() == 3
    bandung = KabKota.objects.get(kode="32.73")
    assert (bandung.jenis, bandung.provinsi.nama) == (JenisKabKota.KOTA, "Jawa Barat")
    assert KabKota.objects.get(kode="32.01").jenis == JenisKabKota.KABUPATEN
    assert AliasProvinsi.objects.get(alias="DKI Jakarta").provinsi.kode == "31"
    assert AliasKabKota.objects.get(alias="Jakarta Pusat").kabkota.kode == "31.71"


@pytest.mark.django_db
def test_seed_aman_dijalankan_ulang(mini_csv):
    call_command("seed_wilayah", file=str(mini_csv))

    def counts():
        return (Provinsi.objects.count(), KabKota.objects.count(), AliasKabKota.objects.count())

    before = counts()
    call_command("seed_wilayah", file=str(mini_csv))
    assert counts() == before


@pytest.mark.django_db
@pytest.mark.skipif(not Path(DEFAULT_CSV).exists(), reason="wilayah.csv belum dibuat")
def test_seed_data_resmi_lengkap():
    call_command("seed_wilayah")
    assert Provinsi.objects.count() == 38
    assert KabKota.objects.count() >= 500
    assert AliasKabKota.objects.filter(alias="Kota Makasar").exists()


@pytest.mark.django_db
def test_alias_unik_tanpa_peduli_huruf(mini_csv):
    call_command("seed_wilayah", file=str(mini_csv))
    target = KabKota.objects.get(kode="32.73")
    AliasKabKota.objects.create(kabkota=target, alias="Bandung Kota")
    with pytest.raises(IntegrityError), transaction.atomic():
        AliasKabKota.objects.create(kabkota=target, alias="bandung kota")


# --- Periode ---


PERIODE_URL = "/referensi/periode/"


def test_periode_akses_per_peran(client, client_as):
    assert client.get(PERIODE_URL).status_code == 302
    assert client_as(Role.VIEWER).get(PERIODE_URL).status_code == 403
    assert client_as(Role.ADMIN).get(PERIODE_URL).status_code == 403
    assert client_as(Role.SUPER_ADMIN).get(PERIODE_URL).status_code == 200


def test_buat_dan_ubah_periode(client_as):
    client = client_as(Role.SUPER_ADMIN)
    response = client.post(
        reverse("referensi:periode_create"),
        {"nama": "Baseline 2026", "jenis": "baseline", "tanggal_mulai": "2026-03-01"},
    )
    assert response.status_code == 302
    periode = Periode.objects.get()
    assert periode.tanggal_mulai == date(2026, 3, 1) and periode.tanggal_selesai is None

    response = client.post(
        reverse("referensi:periode_update", args=[periode.pk]),
        {
            "nama": "Baseline 2026",
            "jenis": "baseline",
            "tanggal_mulai": "2026-03-01",
            "tanggal_selesai": "2026-04-30",
        },
    )
    assert response.status_code == 302
    periode.refresh_from_db()
    assert periode.tanggal_selesai == date(2026, 4, 30)


def test_periode_menolak_tanggal_selesai_sebelum_mulai(client_as):
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("referensi:periode_create"),
        {
            "nama": "Salah",
            "jenis": "monitoring",
            "tanggal_mulai": "2026-05-01",
            "tanggal_selesai": "2026-04-01",
        },
    )
    assert response.status_code == 200
    assert "tidak boleh sebelum" in response.content.decode()
    assert not Periode.objects.exists()


def test_periode_terurut_menurut_tanggal_mulai(client_as):
    Periode.objects.create(nama="Monitoring 1", jenis="monitoring", tanggal_mulai=date(2026, 9, 1))
    Periode.objects.create(nama="Baseline", jenis="baseline", tanggal_mulai=date(2026, 3, 1))
    assert [p.nama for p in Periode.objects.all()] == ["Baseline", "Monitoring 1"]


# --- Daftar wilayah ---


@pytest.mark.django_db
def test_wilayah_filter_dan_cari(client_as, mini_csv):
    call_command("seed_wilayah", file=str(mini_csv))
    client = client_as(Role.SUPER_ADMIN)

    html = client.get("/referensi/wilayah/").content.decode()
    assert "Kota Bandung" in html and "Kabupaten Bogor" in html and "Jakarta Pusat" in html

    html = client.get("/referensi/wilayah/?provinsi=32").content.decode()
    assert "Kota Bandung" in html and "Jakarta Pusat" not in html

    html = client.get("/referensi/wilayah/?q=bogor").content.decode()
    assert "Kabupaten Bogor" in html and "Kota Bandung" not in html


def test_wilayah_ditolak_untuk_admin(client_as):
    assert client_as(Role.ADMIN).get("/referensi/wilayah/").status_code == 403


# --- Admin Django (untuk koreksi data dan alias) ---


@pytest.mark.parametrize("model", ["provinsi", "kabkota", "periode"])
def test_admin_django_dapat_dibuka_super_admin(client_as, model):
    assert client_as(Role.SUPER_ADMIN).get(f"/admin/referensi/{model}/").status_code == 200


def test_admin_django_ditolak_untuk_admin_biasa(client_as):
    assert client_as(Role.ADMIN).get("/admin/referensi/provinsi/").status_code == 302
