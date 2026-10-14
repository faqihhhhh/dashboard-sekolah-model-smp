from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

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

pytestmark = pytest.mark.django_db


def test_hasil_baseline_menyimpan_skor_profil_apa_adanya(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Awal", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    result = HasilBaseline.objects.create(
        sekolah=school,
        periode=period,
        skor_pm=Decimal("73.2500"),
        profil_pm="Berkembang",
        profil_data={"kode_contoh": "nilai sumber"},
    )

    assert result.skor_pm == Decimal("73.2500")
    assert result.skor_kka is None
    assert result.profil_data == {"kode_contoh": "nilai sumber"}
    assert result.history.count() == 1


def test_hasil_baseline_mempertahankan_presisi_skor(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Presisi", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    result = HasilBaseline.objects.create(
        sekolah=school, periode=period, skor_pm=Decimal("2.3552083333")
    )

    result.refresh_from_db()
    assert result.skor_pm == Decimal("2.3552083333")


def test_hasil_baseline_unik_per_sekolah_dan_periode(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Unik", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    HasilBaseline.objects.create(sekolah=school, periode=period)

    with pytest.raises(IntegrityError), transaction.atomic():
        HasilBaseline.objects.create(sekolah=school, periode=period)


def test_hasil_indikator_rating_dan_indikator_tidak_ganda(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Baseline Indikator", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    baseline = HasilBaseline.objects.create(sekolah=school, periode=period)
    indicator = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L3,
        kode="1.1.1",
        nama="Contoh indikator",
        deskripsi="Panduan yang disediakan pemilik program.",
    )
    result = HasilIndikator.objects.create(
        hasil_baseline=baseline,
        indikator=indicator,
        rating=RatingIndikator.PRA_BERKEMBANG,
    )

    assert result.get_rating_display() == "Pra-Berkembang"
    assert result.history.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        HasilIndikator.objects.create(hasil_baseline=baseline, indikator=indicator)

    result.rating = "rating-tidak-valid"
    with pytest.raises(ValidationError):
        result.full_clean()


def test_kamus_mengharuskan_induk_sesuai_level_dan_kerangka():
    parent = KamusIndikator.objects.create(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L1,
        kode="murid",
        nama="Murid",
    )
    child = KamusIndikator(
        kerangka=Kerangka.PM,
        level=LevelIndikator.L2,
        kode="1.1",
        nama="Contoh",
        parent=parent,
    )
    child.full_clean()

    child.parent = None
    with pytest.raises(ValidationError):
        child.full_clean()

    child.parent = KamusIndikator.objects.create(
        kerangka=Kerangka.KKA,
        level=LevelIndikator.L1,
        kode="guru-kka",
        nama="Guru",
    )
    with pytest.raises(ValidationError):
        child.full_clean()


def test_seed_baseline_reference_idempoten():
    call_command("seed_baseline_reference", verbosity=0)
    assert KamusIndikator.objects.count() == 56
    assert PanduanRating.objects.count() == 136
    level_three_count = KamusIndikator.objects.filter(
        level=LevelIndikator.L3, parent__isnull=False
    ).count()
    assert level_three_count == 35

    call_command("seed_baseline_reference", verbosity=0)
    assert KamusIndikator.objects.count() == 56
    assert PanduanRating.objects.count() == 136
