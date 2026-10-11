import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from tests.conftest import PASSWORD

NEW_PASSWORD = "Sandi-Baru-Yang-Kuat-2026"


def create_payload(**overrides):
    data = {
        "full_name": "Siti Aminah",
        "email": "Siti@Example.com",
        "role": Role.ADMIN,
        "password1": NEW_PASSWORD,
        "password2": NEW_PASSWORD,
    }
    data.update(overrides)
    return data


# --- Hak akses: hanya Super Admin ---


@pytest.mark.parametrize("url_name", ["accounts:user_create"])
def test_halaman_tambah_per_peran(client, client_as, url_name):
    url = reverse(url_name)
    assert client.get(url).status_code == 302  # anonim -> login
    for role in (Role.VIEWER, Role.ADMIN):
        assert client_as(role).get(url).status_code == 403
    assert client_as(Role.SUPER_ADMIN).get(url).status_code == 200


@pytest.mark.parametrize("url_name", ["accounts:user_update", "accounts:user_password"])
@pytest.mark.parametrize(("role", "status"), [(Role.VIEWER, 403), (Role.ADMIN, 403)])
def test_ubah_dan_sandi_ditolak_non_super_admin(client_as, make_user, url_name, role, status):
    target = make_user(Role.VIEWER, email="target@example.com")
    client = client_as(role)
    assert client.get(reverse(url_name, args=[target.pk])).status_code == status
    assert client.post(reverse(url_name, args=[target.pk]), {}).status_code == status


# --- Tambah pengguna ---


def test_super_admin_membuat_pengguna(client_as):
    client = client_as(Role.SUPER_ADMIN)
    response = client.post(reverse("accounts:user_create"), create_payload())
    assert response.status_code == 302
    user = User.objects.get(email="siti@example.com")
    assert user.role == Role.ADMIN
    assert user.check_password(NEW_PASSWORD)
    assert user.is_active and not user.is_staff


def test_tambah_menolak_email_ganda_tanpa_peduli_huruf(client_as, make_user):
    make_user(Role.VIEWER, email="siti@example.com")
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_create"), create_payload(email="SITI@example.com")
    )
    assert response.status_code == 200
    assert "sudah terdaftar" in response.content.decode()
    assert User.objects.filter(email__iexact="siti@example.com").count() == 1


def test_tambah_menolak_sandi_tidak_sama(client_as):
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_create"), create_payload(password2="berbeda-sekali-123")
    )
    assert response.status_code == 200
    assert "tidak sama" in response.content.decode()
    assert not User.objects.filter(email="siti@example.com").exists()


def test_tambah_menolak_sandi_lemah(client_as):
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_create"), create_payload(password1="12345678", password2="12345678")
    )
    assert response.status_code == 200
    assert not User.objects.filter(email="siti@example.com").exists()


# --- Ubah pengguna ---


def test_super_admin_mengubah_peran_dan_menonaktifkan_orang_lain(client_as, make_user):
    target = make_user(Role.VIEWER, email="target@example.com")
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_update", args=[target.pk]),
        {"full_name": "Nama Baru", "role": Role.ADMIN},  # is_active tidak dicentang
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert (target.full_name, target.role, target.is_active) == ("Nama Baru", Role.ADMIN, False)
    assert target.email == "target@example.com"  # email tidak bisa diubah


def test_email_tidak_bisa_diubah_lewat_form(client_as, make_user):
    target = make_user(Role.VIEWER, email="target@example.com")
    client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_update", args=[target.pk]),
        {"full_name": "X", "email": "lain@example.com", "role": Role.VIEWER, "is_active": "on"},
    )
    target.refresh_from_db()
    assert target.email == "target@example.com"


def test_super_admin_tidak_bisa_menurunkan_atau_menonaktifkan_diri_sendiri(client, make_user):
    me = make_user(Role.SUPER_ADMIN, email="me@example.com")
    client.force_login(me)
    client.post(
        reverse("accounts:user_update", args=[me.pk]),
        {"full_name": "Saya", "role": Role.VIEWER},  # mencoba turun peran + nonaktif
    )
    me.refresh_from_db()
    assert me.role == Role.SUPER_ADMIN
    assert me.is_active is True
    assert me.full_name == "Saya"  # field lain tetap bisa diubah


# --- Atur kata sandi ---


def test_super_admin_mengatur_ulang_sandi_pengguna_lain(client_as, make_user, client):
    target = make_user(Role.VIEWER, email="target@example.com")
    response = client_as(Role.SUPER_ADMIN).post(
        reverse("accounts:user_password", args=[target.pk]),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.check_password(NEW_PASSWORD)
    assert not target.check_password(PASSWORD)


def test_atur_sandi_diri_sendiri_tidak_membuat_logout(client, make_user):
    me = make_user(Role.SUPER_ADMIN, email="me@example.com")
    client.force_login(me)
    client.post(
        reverse("accounts:user_password", args=[me.pk]),
        {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
    )
    assert client.get(reverse("accounts:user_list")).status_code == 200


def test_atur_sandi_pengguna_tidak_ada_404(client_as):
    response = client_as(Role.SUPER_ADMIN).get(reverse("accounts:user_password", args=[99999]))
    assert response.status_code == 404
