import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.accounts.models import Role
from apps.sekolah.models import Sekolah

LIST = "/sekolah/"


def payload(wilayah, **overrides):
    data = {
        "npsn": "10100001",
        "nama": "SMP Negeri 1 Contoh",
        "jenjang": "SMP",
        "provinsi": wilayah.jabar.pk,
        "kabkota": wilayah.bandung.pk,
        "status": "negeri",
        "pengusul": "dinas",
        "mapel_kka": "pelaksana",
        "jumlah_guru": "30",
    }
    data.update(overrides)
    return data


def payload_from(obj):
    return {
        "npsn": obj.npsn,
        "nama": obj.nama,
        "jenjang": obj.jenjang,
        "provinsi": obj.provinsi_id,
        "kabkota": obj.kabkota_id,
        "status": obj.status,
        "pengusul": obj.pengusul,
        "mapel_kka": obj.mapel_kka,
        "jumlah_guru": obj.jumlah_guru or "",
    }


# --- Model & soft delete ---


@pytest.mark.parametrize("npsn", ["1234567", "123456789", "1234567a", ""])
def test_npsn_harus_8_digit(wilayah, npsn):
    sekolah = Sekolah(
        npsn=npsn, nama="X", provinsi=wilayah.jabar, kabkota=wilayah.bandung,
        status="negeri", pengusul="dinas", mapel_kka="bukan",
    )  # fmt: skip
    with pytest.raises(ValidationError) as error:
        sekolah.full_clean()
    assert "npsn" in error.value.message_dict


def test_kabkota_harus_sesuai_provinsi(wilayah, make_sekolah):
    sekolah = make_sekolah()
    sekolah.kabkota = wilayah.malang  # Malang bukan di Jawa Barat
    with pytest.raises(ValidationError) as error:
        sekolah.full_clean()
    assert "kabkota" in error.value.message_dict


def test_soft_delete_dan_restore(make_sekolah, make_user):
    sekolah = make_sekolah()
    admin = make_user(Role.ADMIN)
    sekolah.soft_delete(admin)
    assert not Sekolah.objects.filter(pk=sekolah.pk).exists()
    assert Sekolah.all_objects.get(pk=sekolah.pk).deleted_by == admin
    sekolah.restore()
    assert Sekolah.objects.filter(pk=sekolah.pk).exists()


# --- Daftar: Guest vs Viewer ---


def test_guest_hanya_melihat_kolom_publik(client, make_sekolah):
    make_sekolah(npsn="10100001", nama="SMP Rahasia Angka", jumlah_guru=777)
    html = client.get(LIST).content.decode()
    assert "SMP Rahasia Angka" in html and "10100001" in html
    assert "Jenjang" not in html
    assert "Jumlah guru tetap" not in html
    assert "777" not in html  # data sensitif tidak pernah ikut terkirim
    assert "Aksi" not in html and "+ Tambah" not in html


def test_viewer_melihat_semua_kolom_tanpa_tombol_ubah(client_as, make_sekolah):
    make_sekolah(jumlah_guru=777)
    html = client_as(Role.VIEWER).get(LIST).content.decode()
    assert "Jumlah guru tetap" in html and "777" in html
    assert "Jenjang" in html and "SMP" in html
    assert "Aksi" not in html and "+ Tambah" not in html


def test_admin_melihat_tombol_aksi(client_as, make_sekolah):
    make_sekolah()
    html = client_as(Role.ADMIN).get(LIST).content.decode()
    assert "+ Tambah" in html and "Riwayat" in html and "Hapus" in html
    assert "Terhapus" not in html  # hanya Super Admin


def test_super_admin_melihat_tombol_terhapus(client_as):
    assert "Terhapus" in client_as(Role.SUPER_ADMIN).get(LIST).content.decode()


def test_cari_dan_filter(client_as, make_sekolah, wilayah):
    make_sekolah(nama="SMP Alpha", status="negeri", pengusul="dinas")
    make_sekolah(nama="SMP Beta", status="swasta", pengusul="mitra", provinsi=wilayah.jatim,
                 kabkota=wilayah.malang)  # fmt: skip
    client = client_as(Role.VIEWER)

    html = client.get(LIST, {"q": "alpha"}).content.decode()
    assert "SMP Alpha" in html and "SMP Beta" not in html
    html = client.get(LIST, {"status": "swasta"}).content.decode()
    assert "SMP Beta" in html and "SMP Alpha" not in html
    html = client.get(LIST, {"provinsi": wilayah.jabar.pk}).content.decode()
    assert "SMP Alpha" in html and "SMP Beta" not in html
    html = client.get(LIST, {"pengusul": "mitra"}).content.decode()
    assert "SMP Beta" in html and "SMP Alpha" not in html


def test_filter_nilai_asing_diabaikan(client, make_sekolah):
    make_sekolah(nama="SMP Alpha")
    response = client.get(LIST, {"provinsi": "abc", "status": "ngawur"})
    assert response.status_code == 200
    assert "SMP Alpha" in response.content.decode()


def test_guest_tidak_bisa_memfilter_kolom_terbatas(client, make_sekolah):
    make_sekolah(nama="SMP Alpha", jumlah_guru=5)
    # jumlah_guru bukan kolom publik dan memang tidak ada di filter; parameter diabaikan
    html = client.get(LIST, {"jumlah_guru": "999"}).content.decode()
    assert "SMP Alpha" in html


def test_paginasi_25_per_halaman(client, make_sekolah):
    for _ in range(30):
        make_sekolah()
    page1 = client.get(LIST).content.decode()
    page2 = client.get(LIST, {"page": 2}).content.decode()
    assert page1.count("SMP Uji") == 25
    assert page2.count("SMP Uji") == 5


# --- Tambah ---


def test_hak_akses_tambah(client, client_as):
    url = reverse("sekolah:create")
    assert client.get(url).status_code == 302
    assert client_as(Role.VIEWER).get(url).status_code == 403
    assert client_as(Role.ADMIN).get(url).status_code == 200


def test_admin_menambah_sekolah_dan_riwayat_mencatat_pelaku(client_as, wilayah, make_user):
    client = client_as(Role.ADMIN)
    response = client.post(reverse("sekolah:create"), payload(wilayah))
    assert response.status_code == 302
    sekolah = Sekolah.objects.get(npsn="10100001")
    assert sekolah.jumlah_guru == 30 and sekolah.jenjang == "SMP"
    first = sekolah.history.get()
    assert first.history_type == "+"
    assert first.history_user.email == "admin@example.com"


def test_tambah_menolak_npsn_salah_dan_ganda(client_as, wilayah, make_sekolah):
    make_sekolah(npsn="10100001")
    client = client_as(Role.ADMIN)
    r1 = client.post(reverse("sekolah:create"), payload(wilayah))  # NPSN sudah ada
    assert r1.status_code == 200 and "sudah terdaftar" in r1.content.decode()
    r2 = client.post(reverse("sekolah:create"), payload(wilayah, npsn="123"))
    assert r2.status_code == 200 and "8 digit" in r2.content.decode()
    assert Sekolah.objects.count() == 1


def test_tambah_menolak_kabkota_di_luar_provinsi(client_as, wilayah):
    response = client_as(Role.ADMIN).post(
        reverse("sekolah:create"), payload(wilayah, kabkota=wilayah.malang.pk)
    )
    assert response.status_code == 200
    assert not Sekolah.objects.exists()


def test_npsn_milik_data_terhapus_diberi_pesan_khusus(client_as, wilayah, make_sekolah):
    make_sekolah(npsn="10100001").soft_delete()
    response = client_as(Role.ADMIN).post(reverse("sekolah:create"), payload(wilayah))
    assert response.status_code == 200
    assert "telah dihapus" in response.content.decode()


# --- Ubah & riwayat ---


def test_ubah_sekolah_dan_riwayat_menampilkan_selisih(client_as, make_sekolah):
    sekolah = make_sekolah(nama="Nama Lama")
    client = client_as(Role.ADMIN)
    data = payload_from(sekolah) | {"nama": "Nama Baru", "jumlah_guru": "99"}
    assert client.post(reverse("sekolah:update", args=[sekolah.pk]), data).status_code == 302

    sekolah.refresh_from_db()
    assert sekolah.nama == "Nama Baru"
    html = client.get(reverse("sekolah:history", args=[sekolah.pk])).content.decode()
    assert "Nama sekolah:" in html and "Nama Lama" in html and "Nama Baru" in html
    assert "Jumlah guru tetap:" in html and "99" in html
    assert "Dibuat" in html and "Diubah" in html


def test_ubah_tanpa_perubahan_tidak_membuat_riwayat(client_as, make_sekolah):
    sekolah = make_sekolah()
    client = client_as(Role.ADMIN)
    response = client.post(
        reverse("sekolah:update", args=[sekolah.pk]), payload_from(sekolah), follow=True
    )
    assert "Tidak ada perubahan" in response.content.decode()
    assert sekolah.history.count() == 1  # hanya catatan pembuatan


def test_ubah_dan_riwayat_ditolak_untuk_viewer(client_as, make_sekolah):
    sekolah = make_sekolah()
    client = client_as(Role.VIEWER)
    for name in ("update", "history", "delete"):
        assert client.get(reverse(f"sekolah:{name}", args=[sekolah.pk])).status_code == 403


# --- Hapus, sampah, pulihkan ---


def test_hapus_butuh_konfirmasi_lalu_menyembunyikan_data(client_as, make_sekolah):
    sekolah = make_sekolah(nama="SMP Akan Dihapus")
    client = client_as(Role.ADMIN)
    url = reverse("sekolah:delete", args=[sekolah.pk])

    assert "Ya, hapus" in client.get(url).content.decode()
    assert Sekolah.objects.filter(pk=sekolah.pk).exists()  # GET tidak menghapus

    assert client.post(url).status_code == 302
    assert "SMP Akan Dihapus" not in client.get(LIST).content.decode()
    deleted = Sekolah.all_objects.get(pk=sekolah.pk)
    assert deleted.is_deleted and deleted.deleted_by.email == "admin@example.com"

    html = client.get(reverse("sekolah:history", args=[sekolah.pk])).content.decode()
    assert ">Dihapus</span>" in html  # entri berjenis "Dihapus" (riwayat data terhapus terlihat)


def test_sampah_dan_pulihkan_hanya_super_admin(client_as, make_sekolah):
    sekolah = make_sekolah(nama="SMP Terhapus")
    sekolah.soft_delete()
    trash = reverse("sekolah:trash")
    restore = reverse("sekolah:restore", args=[sekolah.pk])

    admin = client_as(Role.ADMIN)
    assert admin.get(trash).status_code == 403
    assert admin.post(restore).status_code == 403

    boss = client_as(Role.SUPER_ADMIN)
    assert "SMP Terhapus" in boss.get(trash).content.decode()
    assert boss.post(restore).status_code == 302
    assert Sekolah.objects.filter(pk=sekolah.pk).exists()
    history = boss.get(reverse("sekolah:history", args=[sekolah.pk])).content.decode()
    assert ">Dipulihkan</span>" in history and ">Dihapus</span>" in history


def test_pulihkan_tidak_menerima_get(client_as, make_sekolah):
    sekolah = make_sekolah()
    sekolah.soft_delete()
    response = client_as(Role.SUPER_ADMIN).get(reverse("sekolah:restore", args=[sekolah.pk]))
    assert response.status_code == 405


# --- Dropdown bertingkat (HTMX) ---


def test_opsi_kabkota_hanya_milik_provinsi(client_as, wilayah):
    client = client_as(Role.ADMIN)
    html = client.get(reverse("sekolah:options_kabkota"), {"provinsi": wilayah.jabar.pk})
    text = html.content.decode()
    assert "Kota Bandung" in text and "Kabupaten Bogor" in text
    assert "Kabupaten Malang" not in text

    kosong = client.get(reverse("sekolah:options_kabkota"), {"provinsi": ""}).content.decode()
    assert "Kota Bandung" not in kosong and "Pilih kabupaten/kota" in kosong


def test_opsi_kabkota_ditolak_untuk_viewer(client_as, wilayah):
    response = client_as(Role.VIEWER).get(reverse("sekolah:options_kabkota"))
    assert response.status_code == 403


def test_form_memasang_atribut_htmx_pada_provinsi(client_as):
    html = client_as(Role.ADMIN).get(reverse("sekolah:create")).content.decode()
    assert 'hx-get="/sekolah/opsi-kabkota/"' in html and 'hx-target="#id_kabkota"' in html


# --- Admin Django & data demo ---


def test_admin_django_menampilkan_sekolah_termasuk_terhapus(client_as, make_sekolah):
    make_sekolah(nama="SMP Aktif")
    make_sekolah(nama="SMP Sudah Terhapus").soft_delete()
    html = client_as(Role.SUPER_ADMIN).get("/admin/sekolah/sekolah/").content.decode()
    assert "SMP Aktif" in html and "SMP Sudah Terhapus" in html


def test_demo_hanya_saat_debug(settings, wilayah):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo_sekolah")


def test_demo_membuat_dan_menghapus(settings, wilayah):
    settings.DEBUG = True
    call_command("seed_demo_sekolah", jumlah=12)
    call_command("seed_demo_sekolah", jumlah=12)  # aman diulang
    assert Sekolah.objects.filter(extra__demo=True).count() == 12
    call_command("seed_demo_sekolah", hapus=True)
    assert Sekolah.all_objects.count() == 0
