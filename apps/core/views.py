from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render


def home(request):
    return render(request, "home.html")


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
