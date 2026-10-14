from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Sekolah


@admin.register(Sekolah)
class SekolahAdmin(SimpleHistoryAdmin):
    """Untuk Super Admin: termasuk data terhapus, dan satu-satunya tempat hapus permanen."""

    list_display = ("npsn", "nama", "provinsi", "kabkota", "status", "pengusul", "deleted_at")
    list_filter = ("status", "pengusul", "mapel_kka", "provinsi")
    search_fields = ("npsn", "nama")
    readonly_fields = ("import_batch",)

    def get_queryset(self, request):
        return Sekolah.all_objects.select_related("provinsi", "kabkota")
