from django.contrib import admin

from .models import VideoPraktik


@admin.register(VideoPraktik)
class VideoPraktikAdmin(admin.ModelAdmin):
    actions = ("restore_selected",)
    list_display = ("judul", "sekolah", "kerangka", "dipublikasikan", "deleted_at", "updated_at")
    list_filter = ("kerangka", "dipublikasikan", "deleted_at")
    readonly_fields = ("deleted_at", "deleted_by")
    search_fields = ("judul", "sekolah__nama", "sekolah__npsn")

    def get_queryset(self, request):
        return VideoPraktik.all_objects.all()

    @admin.action(description="Pulihkan video terpilih")
    def restore_selected(self, request, queryset):
        restored = 0
        for video in queryset.filter(deleted_at__isnull=False):
            video._history_user = request.user
            video._change_reason = "Pulihkan dari admin"
            video.restore()
            restored += 1
        self.message_user(request, f"{restored} video berhasil dipulihkan.")
