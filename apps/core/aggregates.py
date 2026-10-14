"""Agregat sekolah bersama untuk halaman Beranda dan endpoint publik."""

from django.db.models import Count, Q

from apps.referensi.models import Provinsi
from apps.sekolah.models import MapelKKA, Pengusul, Sekolah, StatusSekolah


def parse_home_filters(params):
    filters = {}
    province_id = params.get("provinsi", "")
    if province_id.isdigit() and Provinsi.objects.filter(pk=int(province_id)).exists():
        filters["provinsi"] = int(province_id)
    for name, choices in (
        ("status", StatusSekolah.choices),
        ("pengusul", Pengusul.choices),
        ("mapel_kka", MapelKKA.choices),
    ):
        value = params.get(name, "")
        if value in dict(choices):
            filters[name] = value
    return filters


def school_queryset(filters):
    queryset = Sekolah.objects.all()
    if "provinsi" in filters:
        queryset = queryset.filter(provinsi_id=filters["provinsi"])
    for name in ("status", "pengusul", "mapel_kka"):
        if name in filters:
            queryset = queryset.filter(**{name: filters[name]})
    return queryset


def home_aggregates(filters=None):
    filters = filters or {}
    schools = school_queryset(filters)
    totals = schools.aggregate(
        total=Count("pk"),
        negeri=Count("pk", filter=Q(status=StatusSekolah.NEGERI)),
        swasta=Count("pk", filter=Q(status=StatusSekolah.SWASTA)),
        dinas=Count("pk", filter=Q(pengusul=Pengusul.DINAS)),
        mitra=Count("pk", filter=Q(pengusul=Pengusul.MITRA)),
        kka=Count("pk", filter=Q(mapel_kka=MapelKKA.PELAKSANA)),
    )
    breakdown = schools.aggregate(
        dinas_negeri=Count("pk", filter=Q(pengusul=Pengusul.DINAS, status=StatusSekolah.NEGERI)),
        dinas_swasta=Count("pk", filter=Q(pengusul=Pengusul.DINAS, status=StatusSekolah.SWASTA)),
        mitra_negeri=Count("pk", filter=Q(pengusul=Pengusul.MITRA, status=StatusSekolah.NEGERI)),
        mitra_swasta=Count("pk", filter=Q(pengusul=Pengusul.MITRA, status=StatusSekolah.SWASTA)),
    )
    province_filter = Q(sekolah__deleted_at__isnull=True)
    for name, value in filters.items():
        lookup = {"provinsi": "provinsi_id"}.get(name, name)
        province_filter &= Q(**{f"sekolah__{lookup}": value})
    provinces = list(
        Provinsi.objects.annotate(
            total=Count("sekolah", filter=province_filter),
        ).order_by("nama")
    )
    return {"totals": totals, "breakdown": breakdown, "provinsi": provinces}
