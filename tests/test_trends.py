from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from apps.baseline.models import HasilBaseline
from apps.core.trends import build_time_chart
from apps.referensi.models import Periode

pytestmark = pytest.mark.django_db


def test_time_chart_mengagregasi_skor_per_tanggal_periode(make_sekolah):
    first = make_sekolah()
    second = make_sekolah()
    march = Periode.objects.create(
        nama="Periode Grafik Maret", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    april = Periode.objects.create(
        nama="Periode Grafik April", jenis="monitoring", tanggal_mulai=date(2026, 4, 1)
    )
    HasilBaseline.objects.create(sekolah=first, periode=march, skor_pm=Decimal("2.0"))
    HasilBaseline.objects.create(sekolah=second, periode=march, skor_pm=Decimal("4.0"))
    HasilBaseline.objects.create(sekolah=first, periode=april, skor_pm=Decimal("3.0"))

    chart = build_time_chart(
        HasilBaseline.objects.all(),
        time_field="periode",
        value_fields=(("skor_pm", "Skor PM", "#2563eb"),),
    )

    assert not chart.empty
    assert len(chart.labels) == 2
    assert [point.value for point in chart.lines[0].points] == ["3.00", "3.00"]


def test_time_chart_kosong_tanpa_skor(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Periode Grafik Kosong", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    HasilBaseline.objects.create(sekolah=school, periode=period)

    chart = build_time_chart(
        HasilBaseline.objects.all(),
        time_field="periode",
        value_fields=(("skor_pm", "Skor PM", "#2563eb"),),
    )

    assert chart.empty
    assert chart.lines == ()


def test_time_chart_menolak_field_waktu_tanpa_tanggal(make_sekolah):
    school = make_sekolah()
    period = Periode.objects.create(
        nama="Periode Grafik Relasi", jenis="baseline", tanggal_mulai=date(2026, 3, 1)
    )
    HasilBaseline.objects.create(sekolah=school, periode=period)

    with pytest.raises(ImproperlyConfigured):
        build_time_chart(
            HasilBaseline.objects.all(),
            time_field="sekolah",
            value_fields=(("skor_pm", "Skor PM", "#2563eb"),),
        )
