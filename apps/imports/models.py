from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


class ImportBatchStatus(models.TextChoices):
    COMMITTED = "committed", "Berhasil"
    ROLLED_BACK = "rolled_back", "Dibatalkan (Rollback)"


class ImportBatch(TimeStampedModel):
    dataset_key = models.CharField("kunci dataset", max_length=50)
    filename = models.CharField("nama berkas", max_length=255)
    file = models.FileField(
        "berkas asli",
        upload_to="imports/%Y/%m/",
        null=True,
        blank=True,
    )
    sheet_name = models.CharField("nama sheet", max_length=100, blank=True)
    mapping_config = models.JSONField("konfigurasi pemetaan", default=dict, blank=True)

    total_rows = models.PositiveIntegerField("total baris", default=0)
    created_count = models.PositiveIntegerField("baris baru", default=0)
    updated_count = models.PositiveIntegerField("baris diperbarui", default=0)
    unchanged_count = models.PositiveIntegerField("baris tanpa perubahan", default=0)
    error_count = models.PositiveIntegerField("baris error", default=0)
    skipped_count = models.PositiveIntegerField("baris dilewati", default=0)

    status = models.CharField(
        "status",
        max_length=20,
        choices=ImportBatchStatus.choices,
        default=ImportBatchStatus.COMMITTED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="diimpor oleh",
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    rolled_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibatalkan oleh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    rolled_back_at = models.DateTimeField("waktu pembatalan", null=True, blank=True)
    change_log = models.JSONField("catatan perubahan", default=dict, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "batch impor"
        verbose_name_plural = "batch impor"

    def __str__(self):
        return f"Batch #{self.pk} ({self.dataset_key}) - {self.filename}"


class MappingProfile(TimeStampedModel):
    dataset_key = models.CharField("kunci dataset", max_length=50)
    nama = models.CharField("nama profil", max_length=100)
    header_signature = models.JSONField(
        "daftar header",
        default=list,
        help_text="Urutan dan nama header kolom untuk memastikan kecocokan file.",
    )
    config = models.JSONField("konfigurasi pemetaan", default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mapping_profiles",
    )

    class Meta:
        ordering = ["dataset_key", "nama"]
        unique_together = [("dataset_key", "nama")]
        verbose_name = "profil pemetaan"
        verbose_name_plural = "profil pemetaan"

    def __str__(self):
        return f"{self.nama} ({self.dataset_key})"

    def matches_headers(self, available_headers) -> bool:
        """Profil hanya boleh dipakai ulang bila daftar header sama persis."""
        return list(self.header_signature) == list(available_headers)


class ValueAlias(TimeStampedModel):
    dataset_key = models.CharField("kunci dataset", max_length=50)
    field_name = models.CharField("nama field", max_length=50)
    alias = models.CharField(
        "alias",
        max_length=100,
        help_text="Nilai mentah dari file impor.",
    )
    target_value = models.CharField(
        "nilai baku",
        max_length=100,
        help_text="Nilai sah pada pilihan model.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dibuat oleh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["dataset_key", "field_name", "alias"]
        unique_together = [("dataset_key", "field_name", "alias")]
        verbose_name = "alias nilai"
        verbose_name_plural = "alias nilai"

    def __str__(self):
        return f"{self.dataset_key}.{self.field_name}: '{self.alias}' -> '{self.target_value}'"
