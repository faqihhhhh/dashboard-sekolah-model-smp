from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import HasilBaseline, HasilIndikator, KamusIndikator, PanduanRating


@admin.register(HasilBaseline)
class HasilBaselineAdmin(SimpleHistoryAdmin):
    list_display = ("sekolah", "periode", "skor_pm", "profil_pm", "skor_kka", "profil_kka")
    list_filter = ("periode",)
    search_fields = ("sekolah__npsn", "sekolah__nama")
    readonly_fields = ("import_batch",)

    def get_queryset(self, request):
        return HasilBaseline.all_objects.select_related("sekolah", "periode")


@admin.register(KamusIndikator)
class KamusIndikatorAdmin(admin.ModelAdmin):
    list_display = ("kerangka", "level", "kode", "nama", "urutan", "aktif")
    list_filter = ("kerangka", "level", "aktif")
    search_fields = ("kode", "nama", "deskripsi")
    ordering = ("kerangka", "level", "urutan", "kode")


@admin.register(PanduanRating)
class PanduanRatingAdmin(admin.ModelAdmin):
    list_display = ("indikator", "rating")
    list_filter = ("indikator__kerangka", "rating")
    search_fields = ("indikator__kode", "indikator__nama", "deskripsi")


@admin.register(HasilIndikator)
class HasilIndikatorAdmin(SimpleHistoryAdmin):
    list_display = ("hasil_baseline", "indikator", "rating", "deleted_at")
    list_filter = ("rating", "indikator__kerangka", "indikator__level")
    search_fields = (
        "hasil_baseline__sekolah__npsn",
        "hasil_baseline__sekolah__nama",
        "indikator__kode",
    )
    readonly_fields = ("import_batch",)

    def get_queryset(self, request):
        return HasilIndikator.all_objects.select_related("hasil_baseline__sekolah", "indikator")
