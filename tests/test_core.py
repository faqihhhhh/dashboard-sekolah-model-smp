import pytest
from django.urls import reverse

from apps.accounts.models import Role


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
    assert list(response.context["provinsi"]) == [{"provinsi__nama": "Jawa Barat", "total": 2}]
    assert b"jumlah guru" not in response.content.lower()


@pytest.mark.django_db
@pytest.mark.parametrize("role", [None, Role.VIEWER, Role.ADMIN, Role.SUPER_ADMIN])
def test_surat_dukungan_menunjukkan_status_belum_tersedia(client, client_as, role):
    current_client = client_as(role) if role else client
    response = current_client.get(reverse("core:surat_dukungan"))

    assert response.status_code == 200
    assert b"Surat Dukungan" in response.content
    assert b"Data surat belum tersedia" in response.content
    assert b"Belum Unggah" not in response.content
