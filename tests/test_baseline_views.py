import itertools
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
from apps.imports.models import ImportBatch
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
def test_wizard_baseline_meminta_konfirmasi_untuk_kolom_yang_diabaikan(client_as, make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Tinjau Kolom", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    client = client_as("admin")
    url = reverse("baseline:import_wizard")
    upload = SimpleUploadedFile(
        "baseline.csv",
        f"NPSN,Catatan,Kosong\n{school.npsn},Data tambahan,\n".encode(),
        content_type="text/csv",
    )

    client.post(url, {"action": "upload", "encoding": "utf-8", "delimiter": ",", "file": upload})
    client.post(url, {"action": "headers", "header_rows": "1", "first_data_row": "2"})

    response = client.post(
        url,
        {"action": "preview", "periode_id": str(period.pk), "column_0": "npsn"},
    )
    assert response.context["stage"] == "mapping"
    assert "Catatan" in response.context["error"]
    assert "Kosong" in response.context["error"]

    response = client.post(
        url,
        {
            "action": "preview",
            "periode_id": str(period.pk),
            "column_0": "npsn",
            "column_1": "profile_data",
            "column_2": "ignore",
        },
    )
    assert response.context["stage"] == "preview"

    response = client.post(url, {"action": "commit", "error_mode": "stop"})
    assert response.context["stage"] == "done"
    baseline = HasilBaseline.objects.get(sekolah=school, periode=period)
    assert baseline.profil_data == {"Catatan": "Data tambahan"}
    batch = ImportBatch.objects.get(dataset_key="baseline")
    assert batch.mapping_config["ignored_columns"] == ["Kosong"]


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
def test_detail_baseline_menampilkan_nilai_level_satu_dan_dua_sebagai_data_profil(
    client_as, make_sekolah
):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Profil Level", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    baseline = HasilBaseline.objects.create(
        sekolah=school,
        periode=period,
        profil_data={"PM Level 2 | 1.1": "Maju", "PM Level 1 | murid": "Berkembang"},
    )

    response = client_as("viewer").get(reverse("baseline:detail", args=[baseline.pk]))

    assert response.status_code == 200
    assert "PM Level 2 | 1.1" in response.content.decode()
    assert "PM Level 1 | murid" in response.content.decode()


@pytest.mark.django_db
def test_panduan_indikator_dapat_dibaca_guest(client):
    response = client.get(reverse("baseline:guide"))

    assert response.status_code == 200
    assert b"Panduan Indikator" in response.content


_KODE = itertools.count(1)


def _hierarchy(kerangka, level1_kode, level1_nama, level2_nama, leaf_names, *, with_guides=True):
    """Buat satu cabang kamus L1 → L2 → beberapa L3. Kembalikan daftar indikator L3."""
    level1, _ = KamusIndikator.objects.get_or_create(
        kerangka=kerangka,
        level=LevelIndikator.L1,
        kode=level1_kode,
        defaults={"nama": level1_nama, "urutan": {"Murid": 1, "Guru": 2}.get(level1_kode, 3)},
    )
    level2 = KamusIndikator.objects.create(
        kerangka=kerangka,
        level=LevelIndikator.L2,
        kode=f"2.{next(_KODE)}",
        nama=level2_nama,
        parent=level1,
        urutan=1,
    )
    leaves = []
    for index, name in enumerate(leaf_names, start=1):
        leaf = KamusIndikator.objects.create(
            kerangka=kerangka,
            level=LevelIndikator.L3,
            kode=f"3.{next(_KODE)}",
            nama=name,
            parent=level2,
            urutan=index,
        )
        if with_guides:
            PanduanRating.objects.create(
                indikator=leaf, rating=RatingIndikator.MAJU, deskripsi=f"Rubrik maju {name}"
            )
        leaves.append(leaf)
    return leaves


@pytest.fixture
def baseline_lengkap(make_sekolah):
    school = make_sekolah(nama="SMP Tampilan Detail")
    period = Periode.objects.create(
        nama="Baseline Tampilan", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    baseline = HasilBaseline.objects.create(
        sekolah=school, periode=period, skor_pm="2.5", profil_pm="Maju"
    )
    pm_murid = _hierarchy(
        Kerangka.PM, "Murid", "Murid", "Budaya Belajar", ["Memuliakan", "Bermakna"]
    )
    pm_kepala = _hierarchy(
        Kerangka.PM, "Kepala Satpen", "Kepala Satpen", "Pengelolaan Sumber Daya", ["Manajemen"]
    )
    kka_guru = _hierarchy(
        Kerangka.KKA, "Guru", "Guru", "Mengajar secara Efektif", ["Literasi digital"]
    )
    # Indikator KKA Murid tanpa rubrik dan tanpa hasil: tidak boleh tampil.
    kka_murid = _hierarchy(
        Kerangka.KKA, "Murid", "Murid", "Budaya Belajar", ["Projek tanpa sumber"], with_guides=False
    )
    ratings = [
        (pm_murid[0], RatingIndikator.MAJU),
        (pm_murid[1], RatingIndikator.BERKEMBANG),
        (kka_guru[0], RatingIndikator.UNGGUL),
    ]
    for indicator, rating in ratings:
        HasilIndikator.objects.create(hasil_baseline=baseline, indikator=indicator, rating=rating)
    return baseline, {"pm_murid": pm_murid, "pm_kepala": pm_kepala, "kka_murid": kka_murid}


@pytest.mark.django_db
def test_detail_baseline_menampilkan_profil_ringkasan_dan_bagian_bertingkat(
    client_as, baseline_lengkap
):
    baseline, _ = baseline_lengkap

    response = client_as("viewer").get(reverse("baseline:detail", args=[baseline.pk]))
    html = response.content.decode()

    assert response.status_code == 200
    # Profil satuan pendidikan
    assert "Profil Satuan Pendidikan" in html
    assert "SMP Tampilan Detail" in html
    assert "Kota Bandung, Prov. Jawa Barat" in html
    # Bagian bertingkat dengan huruf berurutan lintas PM dan KKA
    assert "A. Keunggulan Belajar Murid" in html
    assert "B. Keunggulan Mengajar Kepala Satuan Pendidikan" in html
    assert "C. Guru — Koding &amp; Kecerdasan Artifisial" in html
    assert "Budaya Belajar" in html
    assert "Memuliakan" in html
    # Badge rating tiap baris
    assert ">Maju<" in html
    assert ">Berkembang<" in html
    assert ">Unggul<" in html
    assert ">Belum diisi<" in html  # PM kepala: berrubrik tetapi belum ada hasil


@pytest.mark.django_db
def test_detail_baseline_menyembunyikan_indikator_tanpa_rubrik_dan_hasil(
    client_as, baseline_lengkap
):
    baseline, _ = baseline_lengkap

    html = client_as("viewer").get(reverse("baseline:detail", args=[baseline.pk])).content.decode()

    assert "Projek tanpa sumber" not in html


@pytest.mark.django_db
def test_ringkasan_detail_menghitung_rating_per_kerangka(client_as, baseline_lengkap):
    baseline, _ = baseline_lengkap

    response = client_as("viewer").get(reverse("baseline:detail", args=[baseline.pk]))
    pm, kka = response.context["blocks"]

    pm_counts = {item["label"]: item["count"] for item in pm["legend"]}
    kka_counts = {item["label"]: item["count"] for item in kka["legend"]}
    assert pm["total"] == 3
    assert pm_counts["Maju"] == 1
    assert pm_counts["Berkembang"] == 1
    assert pm_counts["Belum diisi"] == 1
    assert kka["total"] == 1
    assert kka_counts["Unggul"] == 1
    assert str(pm["skor"]) == "2.5"
    assert pm["profil"] == "Maju"


@pytest.mark.django_db
def test_kontrol_ubah_rating_hanya_dikirim_ke_admin(client_as, baseline_lengkap):
    baseline, leaves = baseline_lengkap
    url = reverse("baseline:detail", args=[baseline.pk])
    field = f'name="rating_{leaves["pm_murid"][0].pk}"'

    viewer_html = client_as("viewer").get(url).content.decode()
    assert field not in viewer_html
    assert 'name="reason"' not in viewer_html

    admin_html = client_as("admin").get(url).content.decode()
    assert field in admin_html
    assert 'name="reason"' in admin_html


@pytest.mark.django_db
def test_detail_baseline_tanpa_rating_menampilkan_pesan_kosong(client_as, make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Kosong", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    baseline = HasilBaseline.objects.create(sekolah=school, periode=period)

    response = client_as("viewer").get(reverse("baseline:detail", args=[baseline.pk]))

    assert response.status_code == 200
    assert "Belum ada rating indikator untuk baseline ini." in response.content.decode()
