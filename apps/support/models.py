import uuid
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, URLValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import SoftDeleteModel
from apps.sekolah.models import Sekolah

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def support_document_path(instance, filename):
    return f"surat-dukungan/{instance.sekolah.npsn}/{uuid.uuid4().hex}.pdf"


class JenisSurat(models.TextChoices):
    REKOMENDASI = "rekomendasi", "Surat Rekomendasi dan Dukungan"
    KESIAPAN = "kesiapan", "Surat Kesiapan dan Komitmen Satuan"


class DokumenDukungan(SoftDeleteModel):
    sekolah = models.ForeignKey(
        Sekolah,
        verbose_name="sekolah",
        on_delete=models.PROTECT,
        related_name="dokumen_dukungan",
    )
    jenis = models.CharField("jenis surat", max_length=20, choices=JenisSurat.choices)
    berkas = models.FileField(
        "berkas PDF",
        upload_to=support_document_path,
        blank=True,
        validators=[FileExtensionValidator(["pdf"])],
    )
    tautan_drive = models.URLField(
        "tautan Google Drive", blank=True, validators=[URLValidator(schemes=["https"])]
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["sekolah__provinsi__kode", "sekolah__nama", "jenis"]
        constraints = [
            models.UniqueConstraint(
                fields=("sekolah", "jenis"),
                condition=models.Q(deleted_at__isnull=True),
                name="uniq_active_support_doc_school_kind",
            )
        ]
        verbose_name = "dokumen surat dukungan"
        verbose_name_plural = "dokumen surat dukungan"

    def clean(self):
        super().clean()
        has_file = bool(self.berkas)
        has_link = bool(self.tautan_drive)
        if has_file == has_link:
            raise ValidationError(
                "Pilih satu sumber dokumen: unggah PDF atau isi tautan Google Drive."
            )
        if has_file:
            if self.berkas.size > MAX_DOCUMENT_BYTES:
                raise ValidationError({"berkas": "Ukuran PDF maksimal 10 MB."})
            self.berkas.open("rb")
            header = self.berkas.read(5)
            self.berkas.seek(0)
            if header != b"%PDF-":
                raise ValidationError({"berkas": "Isi berkas tidak dikenali sebagai dokumen PDF."})
        if has_link and urlsplit(self.tautan_drive).hostname not in {
            "drive.google.com",
            "docs.google.com",
        }:
            raise ValidationError(
                {"tautan_drive": "Tautan harus berasal dari drive.google.com atau docs.google.com."}
            )

    @property
    def tersedia(self):
        return bool(self.berkas or self.tautan_drive)

    def __str__(self):
        return f"{self.get_jenis_display()} — {self.sekolah}"
