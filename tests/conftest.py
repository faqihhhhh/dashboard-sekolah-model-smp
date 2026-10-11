import pytest

from apps.accounts.models import User

PASSWORD = "kata-sandi-uji-123"


@pytest.fixture
def make_user(db):
    def _make(role, email=None, **extra):
        return User.objects.create_user(
            email=email or f"{role}@example.com",
            password=PASSWORD,
            full_name=f"Uji {role}",
            role=role,
            **extra,
        )

    return _make


@pytest.fixture
def client_as(client, make_user):
    """client_as("admin") -> client yang sudah login sebagai Admin."""

    def _login(role):
        client.force_login(make_user(role))
        return client

    return _login


@pytest.fixture
def wilayah(db):
    from types import SimpleNamespace

    from apps.referensi.models import KabKota, Provinsi

    jabar = Provinsi.objects.create(kode="32", nama="Jawa Barat")
    jatim = Provinsi.objects.create(kode="35", nama="Jawa Timur")
    return SimpleNamespace(
        jabar=jabar,
        jatim=jatim,
        bandung=KabKota.objects.create(
            provinsi=jabar, kode="32.73", jenis="kota", nama="Kota Bandung"
        ),
        bogor=KabKota.objects.create(
            provinsi=jabar, kode="32.01", jenis="kabupaten", nama="Kabupaten Bogor"
        ),
        malang=KabKota.objects.create(
            provinsi=jatim, kode="35.07", jenis="kabupaten", nama="Kabupaten Malang"
        ),
    )


@pytest.fixture
def make_sekolah(wilayah):
    import itertools

    from apps.sekolah.models import Sekolah

    counter = itertools.count(1)

    def _make(**overrides):
        n = next(counter)
        data = {
            "npsn": f"{10000000 + n}",
            "nama": f"SMP Uji {n}",
            "provinsi": wilayah.jabar,
            "kabkota": wilayah.bandung,
            "status": "negeri",
            "pengusul": "dinas",
            "mapel_kka": "pelaksana",
            "jumlah_guru": 20 + n,
        }
        data.update(overrides)
        return Sekolah.objects.create(**data)

    return _make
