import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.core.registry import REGISTRY, DatasetSpec, get_spec
from apps.sekolah.models import Sekolah


def test_sekolah_terdaftar():
    spec = get_spec("sekolah")
    assert spec is REGISTRY["sekolah"]
    assert spec.model is Sekolah
    assert spec.natural_key == ("npsn",)


def test_field_publik_adalah_bagian_dari_list():
    spec = get_spec("sekolah")
    assert set(spec.public_fields) <= set(spec.list_fields)
    assert "jumlah_guru" not in spec.public_fields


def test_spec_menolak_field_yang_tidak_ada():
    with pytest.raises(ImproperlyConfigured, match="tidak ada"):
        DatasetSpec(
            key="x",
            label="X",
            model=Sekolah,
            url_namespace="sekolah",
            list_fields=("npsn", "tidak_ada"),
            form_fields=("npsn",),
            public_fields=("npsn",),
        )


def test_spec_menolak_public_di_luar_list():
    with pytest.raises(ImproperlyConfigured, match="public_fields"):
        DatasetSpec(
            key="x",
            label="X",
            model=Sekolah,
            url_namespace="sekolah",
            list_fields=("npsn",),
            form_fields=("npsn",),
            public_fields=("npsn", "nama"),
        )
