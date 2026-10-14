import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import Role
from apps.support.models import MAX_DOCUMENT_BYTES, DokumenDukungan, JenisSurat


@pytest.mark.django_db
@pytest.mark.parametrize("role", [None, Role.VIEWER, Role.ADMIN, Role.SUPER_ADMIN])
def test_dashboard_surat_tampil_ke_semua_peran(client, client_as, make_sekolah, role):
    school = make_sekolah(nama="SMP Contoh Dukungan")
    current_client = client_as(role) if role else client
    response = current_client.get(reverse("support:dashboard"))

    assert response.status_code == 200
    assert b"SMP Contoh Dukungan" in response.content
    assert b"Surat Rekomendasi" in response.content
    assert b"Surat Kesiapan" in response.content
    assert school.npsn.encode() in response.content


@pytest.mark.django_db
def test_guest_melihat_status_tanpa_menerima_tautan_dokumen(client, make_sekolah):
    school = make_sekolah()
    private_url = "https://drive.google.com/file/d/rahasia/view"
    DokumenDukungan.objects.create(
        sekolah=school,
        jenis=JenisSurat.REKOMENDASI,
        tautan_drive=private_url,
    )

    response = client.get(reverse("support:dashboard"))

    assert response.status_code == 200
    assert b"Sudah tersedia" in response.content
    assert b"Belum tersedia" in response.content
    doc_url = reverse("support:open_document", args=[DokumenDukungan.objects.get().pk])
    assert doc_url.encode() not in response.content
    assert private_url.encode() not in response.content


@pytest.mark.django_db
def test_guest_tidak_dapat_membuka_dokumen(client, make_sekolah):
    document = DokumenDukungan.objects.create(
        sekolah=make_sekolah(),
        jenis=JenisSurat.KESIAPAN,
        tautan_drive="https://drive.google.com/file/d/privat/view",
    )

    response = client.get(reverse("support:open_document", args=[document.pk]))

    assert response.status_code == 302
    assert "/masuk/" in response.headers["Location"]


@pytest.mark.django_db
def test_viewer_dapat_membuka_tautan_dokumen(client_as, make_sekolah):
    document = DokumenDukungan.objects.create(
        sekolah=make_sekolah(),
        jenis=JenisSurat.REKOMENDASI,
        tautan_drive="https://drive.google.com/file/d/dokumen/view",
    )

    response = client_as(Role.VIEWER).get(reverse("support:open_document", args=[document.pk]))

    assert response.status_code == 302
    assert response.headers["Location"] == document.tautan_drive


@pytest.mark.django_db
def test_viewer_dapat_membuka_pdf_dari_endpoint_terlindungi(
    client_as, make_sekolah, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    document = DokumenDukungan.objects.create(
        sekolah=make_sekolah(),
        jenis=JenisSurat.KESIAPAN,
        berkas=SimpleUploadedFile(
            "surat.pdf", b"%PDF-1.4\nisi uji", content_type="application/pdf"
        ),
    )

    response = client_as(Role.VIEWER).get(reverse("support:open_document", args=[document.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content).startswith(b"%PDF-")


@pytest.mark.django_db
def test_ringkasan_empat_kategori_dan_chart_kumulatif(client, make_sekolah):
    school = make_sekolah(pengusul="dinas")
    DokumenDukungan.objects.create(
        sekolah=school,
        jenis=JenisSurat.REKOMENDASI,
        tautan_drive="https://drive.google.com/file/d/ringkasan/view",
    )

    response = client.get(reverse("support:dashboard"))

    summaries = response.context["summaries"]
    assert len(summaries) == 4
    assert summaries[0]["eligible"] == 1
    assert summaries[0]["available"] == 1
    assert summaries[0]["percent"] == 100
    assert response.context["chart"]["empty"] is False
    assert len(response.context["chart"]["lines"]) == 4
    assert "Perkembangan dokumen" in response.content.decode()


@pytest.mark.django_db
def test_admin_dapat_mengunggah_pdf(client_as, make_sekolah, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    school = make_sekolah()
    response = client_as(Role.ADMIN).post(
        reverse("support:manage_document", args=[school.pk, JenisSurat.REKOMENDASI]),
        {
            "sekolah": school.pk,
            "jenis": JenisSurat.REKOMENDASI,
            "berkas": SimpleUploadedFile(
                "surat.pdf", b"%PDF-1.4\nisi uji", content_type="application/pdf"
            ),
            "tautan_drive": "",
        },
    )

    assert response.status_code == 302
    document = DokumenDukungan.objects.get(sekolah=school, jenis=JenisSurat.REKOMENDASI)
    assert document.berkas
    assert document.berkas.name.startswith(f"surat-dukungan/{school.npsn}/")


@pytest.mark.django_db
def test_admin_ditolak_jika_pdf_hanya_ekstensi(client_as, make_sekolah):
    school = make_sekolah()
    response = client_as(Role.ADMIN).post(
        reverse("support:manage_document", args=[school.pk, JenisSurat.KESIAPAN]),
        {
            "sekolah": school.pk,
            "jenis": JenisSurat.KESIAPAN,
            "berkas": SimpleUploadedFile("palsu.pdf", b"bukan pdf", content_type="application/pdf"),
            "tautan_drive": "",
        },
    )

    assert response.status_code == 200
    assert b"Isi berkas tidak dikenali sebagai dokumen PDF" in response.content
    assert not DokumenDukungan.objects.filter(sekolah=school).exists()


@pytest.mark.django_db
def test_admin_tidak_dapat_membuka_form_pengelolaan(client_as, make_sekolah):
    school = make_sekolah()
    response = client_as(Role.VIEWER).get(
        reverse("support:manage_document", args=[school.pk, JenisSurat.KESIAPAN])
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_dapat_menghapus_dan_super_admin_memulihkan_dokumen(client_as, make_sekolah):
    school = make_sekolah()
    document = DokumenDukungan.objects.create(
        sekolah=school,
        jenis=JenisSurat.REKOMENDASI,
        tautan_drive="https://drive.google.com/file/d/arsip/view",
    )
    url = reverse("support:manage_document", args=[school.pk, JenisSurat.REKOMENDASI])

    response = client_as(Role.ADMIN).post(url, {"action": "hapus"})
    assert response.status_code == 302
    document.refresh_from_db()
    assert document.is_deleted

    response = client_as(Role.SUPER_ADMIN).post(url, {"action": "pulihkan"})
    assert response.status_code == 302
    document.refresh_from_db()
    assert not document.is_deleted


@pytest.mark.django_db
def test_pdf_di_atas_10_mb_ditolak(client_as, make_sekolah):
    school = make_sekolah()
    response = client_as(Role.ADMIN).post(
        reverse("support:manage_document", args=[school.pk, JenisSurat.KESIAPAN]),
        {
            "sekolah": school.pk,
            "jenis": JenisSurat.KESIAPAN,
            "berkas": SimpleUploadedFile(
                "besar.pdf",
                b"%PDF-" + b"x" * MAX_DOCUMENT_BYTES,
                content_type="application/pdf",
            ),
            "tautan_drive": "",
        },
    )

    assert response.status_code == 200
    assert b"Ukuran PDF maksimal 10 MB" in response.content
    assert not DokumenDukungan.objects.filter(sekolah=school).exists()


@pytest.mark.django_db
def test_tautan_drive_harus_https_dari_google(make_sekolah):
    document = DokumenDukungan(
        sekolah=make_sekolah(),
        jenis=JenisSurat.REKOMENDASI,
        tautan_drive="https://example.com/file.pdf",
    )

    with pytest.raises(ValidationError) as error:
        document.full_clean()

    assert "tautan_drive" in error.value.message_dict
