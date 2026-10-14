from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.baseline.models import HasilBaseline, KamusIndikator, Kerangka, LevelIndikator
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
