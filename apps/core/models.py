from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """Manager bawaan: hanya data yang belum dihapus."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diubah", auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Data tidak benar-benar dihapus: hanya ditandai, dan dapat dipulihkan Super Admin."""

    deleted_at = models.DateTimeField("dihapus pada", null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="dihapus oleh",
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = SoftDeleteManager()  # pertama = manager bawaan: hanya yang aktif
    all_objects = models.Manager()  # semua, termasuk yang sudah dihapus

    class Meta:
        abstract = True

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, user=None):
        self.deleted_at = timezone.now()
        self.deleted_by = user if getattr(user, "is_authenticated", False) else None
        self.save()

    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save()
