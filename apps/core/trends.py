"""Pembentukan seri waktu untuk grafik yang dirender server-side."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.formats import date_format


@dataclass(frozen=True)
class TrendPoint:
    label: str
    value: str
    x: float
    y: float


@dataclass(frozen=True)
class TrendLabel:
    label: str
    x: float


@dataclass(frozen=True)
class TrendLine:
    name: str
    color: str
    points: tuple[TrendPoint, ...]


@dataclass(frozen=True)
class TimeChart:
    labels: tuple[TrendLabel, ...]
    lines: tuple[TrendLine, ...]
    empty: bool


def _date_lookup(queryset, time_field: str) -> str:
    field = queryset.model._meta.get_field(time_field)
    if isinstance(field, models.DateTimeField | models.DateField):
        return time_field
    if field.is_relation and hasattr(field.related_model, "_meta"):
        try:
            date_field = field.related_model._meta.get_field("tanggal_mulai")
        except Exception as error:
            raise ImproperlyConfigured(
                f"Field waktu relasi '{time_field}' harus memiliki tanggal_mulai."
            ) from error
        if isinstance(date_field, models.DateField | models.DateTimeField):
            return f"{time_field}__tanggal_mulai"
    raise ImproperlyConfigured(
        f"Field waktu '{time_field}' harus berupa tanggal atau relasi Periode."
    )


def build_time_chart(
    queryset,
    *,
    time_field: str,
    value_fields: tuple[tuple[str, str, str], ...],
) -> TimeChart:
    """Agregasikan field angka per waktu dan siapkan titik SVG.

    `value_fields` berisi (nama field, label, warna). Untuk beberapa record di periode sama,
    nilai yang ditampilkan adalah rata-rata; nilai asli di database tidak diubah.
    """
    date_field = _date_lookup(queryset, time_field)
    fields = {field.name: field for field in queryset.model._meta.fields}
    for name, _label, _color in value_fields:
        field = fields.get(name)
        if not isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField)):
            raise ImproperlyConfigured(f"Field grafik '{name}' harus berupa angka.")

    rows = queryset.order_by(date_field).values_list(
        date_field, *(name for name, _, _ in value_fields)
    )
    by_date: dict[date | datetime, list[list[float]]] = defaultdict(
        lambda: [[] for _ in value_fields]
    )
    for row in rows:
        when = row[0]
        if when is None:
            continue
        if isinstance(when, datetime):
            when = when.date()
        for index, value in enumerate(row[1:]):
            if value is not None:
                by_date[when][index].append(float(value))

    dates = sorted(by_date)
    labels = tuple(
        TrendLabel(
            label=date_format(when, "M Y"),
            x=50.0 if len(dates) == 1 else round(index * 100 / (len(dates) - 1), 2),
        )
        for index, when in enumerate(dates)
    )
    averages = [
        [sum(values) / len(values) if values else None for values in by_date[when]]
        for when in dates
    ]
    all_values = [value for row in averages for value in row if value is not None]
    if not all_values:
        return TimeChart(labels=labels, lines=(), empty=True)

    low = min(all_values)
    high = max(all_values)
    if low == high:
        padding = max(abs(low) * 0.1, 1.0)
        low -= padding
        high += padding
    else:
        padding = (high - low) * 0.08
        low -= padding
        high += padding

    lines = []
    for series_index, (_field, label, color) in enumerate(value_fields):
        points = []
        for date_index, value_row in enumerate(averages):
            value = value_row[series_index]
            if value is None:
                continue
            x = 50.0 if len(dates) == 1 else date_index * 100 / (len(dates) - 1)
            y = 100 - ((value - low) * 100 / (high - low))
            points.append(
                TrendPoint(
                    label=labels[date_index].label,
                    value=f"{value:.2f}",
                    x=round(x, 2),
                    y=round(y, 2),
                )
            )
        lines.append(TrendLine(name=label, color=color, points=tuple(points)))

    return TimeChart(labels=labels, lines=tuple(lines), empty=False)
