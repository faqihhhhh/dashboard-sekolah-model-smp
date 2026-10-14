import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.accounts.permissions import has_role
from tests.conftest import PASSWORD

USER_LIST = "/pengguna/"


# --- Model ---


@pytest.mark.django_db
def test_email_disimpan_huruf_kecil_dan_unik():
    User.objects.create_user(email="Budi@Example.COM", password=PASSWORD, full_name="Budi")
    assert User.objects.get().email == "budi@example.com"
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="budi@example.com", password=PASSWORD, full_name="Budi 2")


@pytest.mark.django_db
def test_is_staff_mengikuti_peran():
    user = User.objects.create_user(
        email="a@example.com", password=PASSWORD, full_name="A", role=Role.SUPER_ADMIN
    )
    assert user.is_staff and user.is_superuser
    user.role = Role.ADMIN
    user.save()
    user.refresh_from_db()
    assert not user.is_staff and not user.is_superuser


@pytest.mark.django_db
def test_createsuperuser_menjadi_super_admin():
    user = User.objects.create_superuser(
        email="root@example.com", password=PASSWORD, full_name="Root"
    )
    assert user.role == Role.SUPER_ADMIN


# --- has_role ---


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "min_role", "expected"),
    [
        (Role.VIEWER, Role.VIEWER, True),
        (Role.VIEWER, Role.ADMIN, False),
        (Role.ADMIN, Role.VIEWER, True),
        (Role.ADMIN, Role.ADMIN, True),
        (Role.ADMIN, Role.SUPER_ADMIN, False),
        (Role.SUPER_ADMIN, Role.ADMIN, True),
    ],
)
def test_has_role(make_user, role, min_role, expected):
    assert has_role(make_user(role), min_role) is expected


@pytest.mark.django_db
def test_has_role_menolak_anonim_dan_nonaktif(make_user):
    from django.contrib.auth.models import AnonymousUser

    assert has_role(AnonymousUser(), Role.VIEWER) is False
    assert has_role(None, Role.VIEWER) is False
    assert has_role(make_user(Role.SUPER_ADMIN, is_active=False), Role.VIEWER) is False


# --- Matriks akses halaman Pengguna (hanya Super Admin) ---


def test_pengguna_anonim_diarahkan_ke_login(client):
    response = client.get(USER_LIST)
    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.parametrize(
    ("role", "status"),
    [(Role.VIEWER, 403), (Role.ADMIN, 403), (Role.SUPER_ADMIN, 200)],
)
def test_pengguna_per_peran(client_as, role, status):
    assert client_as(role).get(USER_LIST).status_code == status


# --- Login / logout ---


@pytest.mark.django_db
def test_halaman_login_tampil(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert "Kata sandi" in response.content.decode()


@pytest.mark.django_db
def test_login_berhasil_walau_email_huruf_besar(client, make_user):
    make_user(Role.ADMIN, email="admin@example.com")
    response = client.post(
        reverse("accounts:login"), {"username": " ADMIN@Example.com ", "password": PASSWORD}
    )
    assert response.status_code == 302
    assert response.url == reverse("core:home")
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_login_gagal_password_salah(client, make_user):
    make_user(Role.ADMIN, email="admin@example.com")
    response = client.post(
        reverse("accounts:login"), {"username": "admin@example.com", "password": "salah"}
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_ditolak_untuk_akun_nonaktif(client, make_user):
    make_user(Role.VIEWER, email="off@example.com", is_active=False)
    client.post(reverse("accounts:login"), {"username": "off@example.com", "password": PASSWORD})
    assert "_auth_user_id" not in client.session


def test_logout_harus_post(client_as):
    client = client_as(Role.VIEWER)
    assert client.get(reverse("accounts:logout")).status_code == 405
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


# --- Tampilan per peran ---


@pytest.mark.django_db
def test_guest_melihat_tombol_masuk_dan_tanpa_menu_pengguna(client):
    html = client.get(reverse("core:home")).content.decode()
    assert "Masuk" in html
    assert "Keluar" not in html
    assert "/pengguna/" not in html


def test_super_admin_melihat_menu_pengguna(client_as):
    html = client_as(Role.SUPER_ADMIN).get(reverse("core:home")).content.decode()
    assert "Keluar" in html
    assert "/pengguna/" in html


def test_admin_tidak_melihat_menu_pengguna(client_as):
    html = client_as(Role.ADMIN).get(reverse("core:home")).content.decode()
    assert "/pengguna/" not in html
