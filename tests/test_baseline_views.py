from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.baseline.models import (
    HasilBaseline,
    HasilIndikator,
    KamusIndikator,
    Kerangka,
    LevelIndikator,
    PanduanRating,
    RatingIndikator,
)
from apps.referensi.models import Periode


@pytest.mark.django_db
def test_guest_diarahkan_login_dari_wizard_baseline(client):
    response = client.get(reverse("baseline:import_wizard"))

    assert response.status_code == 302
    assert response.url.startswith("/masuk/")


@pytest.mark.django_db
def test_viewer_ditolak_dari_wizard_baseline(client_as):
    client = client_as("viewer")

    response = client.get(reverse("baseline:import_wizard"))

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["admin", "super_admin"])
def test_admin_dan_super_admin_dapat_membuka_wizard_baseline(client_as, role):
    client = client_as(role)

    response = client.get(reverse("baseline:import_wizard"))

    assert response.status_code == 200
    assert "Impor Baseline Sekolah" in response.content.decode()


@pytest.mark.django_db
def test_admin_dapat_upload_pemetaan_dry_run_dan_commit_baseline(
    client_as, make_sekolah, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Wizard", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Indikator contoh",
    )
    client = client_as("admin")
    url = reverse("baseline:import_wizard")
    upload = SimpleUploadedFile(
        "baseline.csv",
        f"NPSN,Skor PM,Indikator 1\n{school.npsn},2.5,Maju\n".encode(),
        content_type="text/csv",
    )

    response = client.post(
        url,
        {"action": "upload", "encoding": "utf-8", "delimiter": ",", "file": upload},
    )
    assert response.context["stage"] == "headers"

    response = client.post(
        url,
        {"action": "headers", "header_rows": "1", "first_data_row": "2"},
    )
    assert response.context["stage"] == "mapping", response.context["error"]

    response = client.post(
        url,
        {
            "action": "preview",
            "periode_id": str(period.pk),
            "column_0": "npsn",
            "column_1": "summary:skor_pm",
            "column_2": f"indicator:{indicator.pk}",
        },
    )
    assert response.context["stage"] == "preview"
    assert response.context["preview"].counts()["create"] == 1

    response = client.post(url, {"action": "commit", "error_mode": "stop"})

    assert response.context["stage"] == "done"
    assert HasilBaseline.objects.filter(sekolah=school, periode=period).exists()


@pytest.mark.django_db
def test_guest_hanya_menerima_agregat_baseline(make_sekolah, client):
    school = make_sekolah(nama="SMP Data Terbatas")
    period = Periode.objects.create(
        nama="Baseline Publik", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Indikator contoh",
    )
    PanduanRating.objects.create(
        indikator=indicator,
        rating=RatingIndikator.MAJU,
        deskripsi="Panduan rating yang bersifat publik.",
    )
    baseline = HasilBaseline.objects.create(sekolah=school, periode=period)
    HasilIndikator.objects.create(
        hasil_baseline=baseline, indikator=indicator, rating=RatingIndikator.MAJU
    )

    response = client.get(reverse("baseline:dashboard"), {"periode": period.pk})

    assert response.status_code == 200
    assert b"SMP Data Terbatas" not in response.content
    assert school.npsn.encode() not in response.content
    assert response.context["baseline_count"] == 1
    assert b"Masuk sebagai Viewer" in response.content


@pytest.mark.django_db
def test_detail_baseline_dan_edit_rating_dibatasi_peran(make_sekolah, make_user, client):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Akses Detail", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Indikator contoh",
    )
    baseline = HasilBaseline.objects.create(sekolah=school, periode=period)
    result = HasilIndikator.objects.create(
        hasil_baseline=baseline, indikator=indicator, rating=RatingIndikator.MAJU
    )
    url = reverse("baseline:detail", args=[baseline.pk])

    assert client.get(url).status_code == 302
    client.force_login(make_user("viewer"))
    assert client.get(url).status_code == 200
    assert client.post(url, {f"rating_{indicator.pk}": "unggul"}).status_code == 403

    admin = make_user("admin")
    client.force_login(admin)
    response = client.post(
        url,
        {f"rating_{indicator.pk}": "unggul", "reason": "Koreksi setelah verifikasi"},
    )
    assert response.status_code == 302
    result.refresh_from_db()
    assert result.rating == RatingIndikator.UNGGUL
    assert result.history.first().history_user == admin


@pytest.mark.django_db
def test_panduan_indikator_dapat_dibaca_guest(client):
    response = client.get(reverse("baseline:guide"))

    assert response.status_code == 200
    assert b"Panduan Indikator" in response.content
