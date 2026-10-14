from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from apps.baseline.models import HasilBaseline
from apps.core.aggregates import home_aggregates, parse_home_filters
from apps.referensi.models import Provinsi
from apps.sekolah.models import MapelKKA, Pengusul, StatusSekolah


def home(request):
    filters = parse_home_filters(request.GET)
    aggregates = home_aggregates(filters)
    return render(
        request,
        "home.html",
        {
            **aggregates,
            "filters": filters,
            "provinsi_options": Provinsi.objects.all(),
            "status_options": StatusSekolah.choices,
            "pengusul_options": Pengusul.choices,
            "mapel_options": MapelKKA.choices,
            "baseline_count": HasilBaseline.objects.count(),
        },
    )


def home_aggregate(request):
    """Endpoint publik berisi agregat; tidak mengirim baris sekolah atau kolom terbatas."""
    data = home_aggregates(parse_home_filters(request.GET))
    return JsonResponse(
        {
            "totals": data["totals"],
            "breakdown": data["breakdown"],
            "provinsi": [
                {"kode": item.kode, "nama": item.nama, "total": item.total}
                for item in data["provinsi"]
            ],
        }
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
