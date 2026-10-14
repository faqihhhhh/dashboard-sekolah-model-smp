from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from apps.sekolah.models import MapelKKA, Pengusul, Sekolah, StatusSekolah


def home(request):
    totals = Sekolah.objects.aggregate(
        total=Count("pk"),
        negeri=Count("pk", filter=Q(status=StatusSekolah.NEGERI)),
        swasta=Count("pk", filter=Q(status=StatusSekolah.SWASTA)),
        dinas=Count("pk", filter=Q(pengusul=Pengusul.DINAS)),
        mitra=Count("pk", filter=Q(pengusul=Pengusul.MITRA)),
        kka=Count("pk", filter=Q(mapel_kka=MapelKKA.PELAKSANA)),
    )
    breakdown = Sekolah.objects.aggregate(
        dinas_negeri=Count("pk", filter=Q(pengusul=Pengusul.DINAS, status=StatusSekolah.NEGERI)),
        dinas_swasta=Count("pk", filter=Q(pengusul=Pengusul.DINAS, status=StatusSekolah.SWASTA)),
        mitra_negeri=Count("pk", filter=Q(pengusul=Pengusul.MITRA, status=StatusSekolah.NEGERI)),
        mitra_swasta=Count("pk", filter=Q(pengusul=Pengusul.MITRA, status=StatusSekolah.SWASTA)),
    )
    provinsi = (
        Sekolah.objects.values("provinsi__nama")
        .annotate(total=Count("pk"))
        .order_by("-total", "provinsi__nama")[:10]
    )
    return render(
        request, "home.html", {"totals": totals, "breakdown": breakdown, "provinsi": provinsi}
    )


def surat_dukungan(request):
    return render(request, "core/surat_dukungan.html")


def healthz(request):
    """Dipakai Docker/Caddy/monitoring untuk memeriksa aplikasi dan database hidup."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database = "ok"
    except Exception:
        database = "error"

    ok = database == "ok"
    return JsonResponse(
        {"status": "ok" if ok else "error", "database": database},
        status=200 if ok else 503,
    )
