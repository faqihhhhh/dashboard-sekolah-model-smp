from io import BytesIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import load_workbook

from apps.accounts.models import Role
from apps.imports.models import ImportBatch, ImportBatchStatus
from apps.referensi.models import AliasKabKota
from apps.sekolah.models import Sekolah

pytestmark = pytest.mark.django_db


def test_wizard_hanya_admin(client, make_user):
    url = reverse("imports:wizard", args=["sekolah"])
    response = client.get(url)
    assert response.status_code == 302
    assert "/masuk/" in response.url

    client.force_login(make_user(Role.VIEWER))
    assert client.get(url).status_code == 403

    client.force_login(make_user(Role.SUPER_ADMIN))
    assert client.get(url).status_code == 200


def test_wizard_impor_csv_sampai_commit(client, make_user, wilayah, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    admin = make_user(Role.ADMIN)
    client.force_login(admin)
    url = reverse("imports:wizard", args=["sekolah"])

    upload = SimpleUploadedFile(
        "sekolah.csv",
        (
            b"NPSN,Nama,Kab/Kota,Status,Pengusul,Mapel KKA\n"
            b"12345678,SMP Contoh,Kota Bandung,Negeri,Dinas Pendidikan,Pelaksana\n"
        ),
        content_type="text/csv",
    )
    response = client.post(
        url,
        {"action": "upload", "encoding": "utf-8", "delimiter": ",", "file": upload},
    )
    assert response.status_code == 200
    assert response.context["stage"] == "headers"

    response = client.post(
        url,
        {
            "action": "headers",
            "header_rows": "1",
            "fill_right_rows": "",
            "first_data_row": "2",
        },
    )
    assert response.context["stage"] == "mapping", response.context["error"]

    response = client.post(
        url,
        {
            "action": "preview",
            "column_0": "npsn",
            "column_1": "nama",
            "column_2": "kabkota",
            "column_3": "status",
            "column_4": "pengusul",
            "column_5": "mapel_kka",
        },
    )
    assert response.context["stage"] == "preview"
    assert response.context["preview"].counts()["create"] == 1
    assert b"SMP Contoh" in response.content

    response = client.post(url, {"action": "commit", "error_mode": "stop"})
    assert response.context["stage"] == "done"
    assert Sekolah.objects.filter(npsn="12345678", nama="SMP Contoh").exists()
    batch = ImportBatch.objects.get(dataset_key="sekolah")
    assert batch.created_by == admin
    assert batch.file
    assert (tmp_path / "import-staging").exists()


def test_wizard_menerapkan_dan_menyimpan_alias_kabkota(
    client, make_user, wilayah, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    client.force_login(make_user(Role.ADMIN))
    url = reverse("imports:wizard", args=["sekolah"])
    upload = SimpleUploadedFile(
        "sekolah.csv",
        (
            b"NPSN,Nama,Provinsi,Kab/Kota,Status,Pengusul,Mapel KKA\n"
            b"12345679,SMP Bogor,Jawa Timur,Kab. Bogor,Negeri,Dinas Pendidikan,Pelaksana\n"
        ),
        content_type="text/csv",
    )
    client.post(
        url,
        {"action": "upload", "encoding": "utf-8", "delimiter": ",", "file": upload},
    )
    client.post(
        url,
        {
            "action": "headers",
            "header_rows": "1",
            "fill_right_rows": "",
            "first_data_row": "2",
        },
    )
    response = client.post(
        url,
        {
            "action": "preview",
            "column_0": "npsn",
            "column_1": "nama",
            "column_2": "provinsi",
            "column_3": "kabkota",
            "column_4": "status",
            "column_5": "pengusul",
            "column_6": "mapel_kka",
        },
    )
    assert response.context["preview"].counts()["error"] == 1
    assert b"Cari kabupaten/kota..." in response.content
    response = client.post(
        url,
        {"action": "resolve", "alias_kabkota_Kab. Bogor": "Kabupaten Bogor"},
    )
    assert response.context["preview"].counts()["error"] == 0
    assert response.context["preview"].rows[0].values["provinsi"] == wilayah.jabar

    response = client.post(url, {"action": "commit", "error_mode": "stop"})
    assert response.context["stage"] == "done"
    assert AliasKabKota.objects.get(alias="Kab. Bogor").kabkota == wilayah.bogor


def test_batch_history_file_error_report_dan_rollback(client, make_user, make_sekolah):
    admin = make_user(Role.ADMIN)
    client.force_login(admin)
    school = make_sekolah()
    batch = ImportBatch.objects.create(
        dataset_key="sekolah",
        filename="sumber.csv",
        created_by=admin,
        total_rows=2,
        created_count=1,
        skipped_count=1,
        error_count=1,
        change_log={
            "created_pks": [school.pk],
            "updated": [],
            "errors": [{"row": 3, "message": "NPSN wajib"}],
        },
    )
    batch.file.save("sumber.csv", ContentFile(b"NPSN,Nama\n12345678,Contoh\n"), save=True)

    response = client.get(reverse("imports:history"))
    assert response.status_code == 200
    assert b"Riwayat Impor" in response.content

    response = client.get(reverse("imports:batch_file", args=[batch.pk]))
    assert response.status_code == 200
    assert response["Content-Disposition"].endswith('filename="sumber.csv"')
    assert b"NPSN,Nama" in b"".join(response.streaming_content)

    response = client.get(reverse("imports:error_report", args=[batch.pk]))
    report = load_workbook(BytesIO(response.content), read_only=True)
    assert list(report.active.values)[1] == (3, "NPSN wajib")

    response = client.post(reverse("imports:rollback", args=[batch.pk]), {"confirm": "1"})
    assert response.status_code == 302
    batch.refresh_from_db()
    school.refresh_from_db()
    assert batch.status == ImportBatchStatus.ROLLED_BACK
    assert school.is_deleted


def test_admin_tidak_dapat_rollback_batch_milik_admin_lain(client, make_user, make_sekolah):
    pemilik = make_user(Role.ADMIN, email="pemilik@example.com")
    admin_lain = make_user(Role.ADMIN, email="admin-lain@example.com")
    school = make_sekolah()
    batch = ImportBatch.objects.create(
        dataset_key="sekolah",
        filename="sumber.csv",
        created_by=pemilik,
        change_log={"created_pks": [school.pk], "updated": []},
    )
    client.force_login(admin_lain)
    response = client.post(reverse("imports:rollback", args=[batch.pk]), {"confirm": "1"})
    assert response.status_code == 302
    batch.refresh_from_db()
    school.refresh_from_db()
    assert batch.status == ImportBatchStatus.COMMITTED
    assert not school.is_deleted


def test_riwayat_dan_file_batch_tidak_dapat_diakses_guest_atau_viewer(
    client, make_user, make_sekolah
):
    admin = make_user(Role.ADMIN)
    batch = ImportBatch.objects.create(
        dataset_key="sekolah",
        filename="rahasia.csv",
        created_by=admin,
        change_log={},
    )
    batch.file.save("rahasia.csv", ContentFile(b"data internal"), save=True)
    history_url = reverse("imports:history")
    file_url = reverse("imports:batch_file", args=[batch.pk])

    assert client.get(history_url).status_code == 302
    assert client.get(file_url).status_code == 302

    client.force_login(make_user(Role.VIEWER))
    assert client.get(history_url).status_code == 403
    assert client.get(file_url).status_code == 403
