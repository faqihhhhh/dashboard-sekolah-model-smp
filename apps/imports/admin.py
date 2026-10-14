from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ImportBatch, MappingProfile, ValueAlias


@admin.register(ImportBatch)
class ImportBatchAdmin(SimpleHistoryAdmin):
    list_display = (
        "id",
        "dataset_key",
        "filename",
        "status",
        "created_by",
        "created_at",
        "total_rows",
        "created_count",
        "updated_count",
        "unchanged_count",
        "error_count",
    )
    list_filter = ("dataset_key", "status", "created_at")
    search_fields = ("filename", "dataset_key", "created_by__email")
    readonly_fields = (
        "created_at",
        "updated_at",
        "rolled_back_at",
        "rolled_back_by",
        "change_log",
    )


@admin.register(MappingProfile)
class MappingProfileAdmin(admin.ModelAdmin):
    list_display = ("nama", "dataset_key", "created_by", "created_at")
    list_filter = ("dataset_key",)
    search_fields = ("nama", "dataset_key")


@admin.register(ValueAlias)
class ValueAliasAdmin(admin.ModelAdmin):
    list_display = (
        "dataset_key",
        "field_name",
        "alias",
        "target_value",
        "created_by",
        "created_at",
    )
    list_filter = ("dataset_key", "field_name")
    search_fields = ("alias", "target_value")
