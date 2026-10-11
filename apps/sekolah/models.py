from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import SoftDeleteModel
from apps.referensi.models import KabKota, Provinsi


class Jenjang(models.TextChoices):
    SMP = "SMP", "SMP"


class StatusSekolah(models.TextChoices):
    NEGERI = "negeri", "Negeri"
    SWASTA = "swasta", "Swasta"


class Pengusul(models.TextChoices):
    DINAS = "dinas", "Dinas Pendidikan"
    MITRA = "mitra", "Mitra"


class MapelKKA(models.TextChoices):
    PELAKSANA = "pelaksana", "Pelaksana"
    BUKAN = "bukan", "Bukan pelaksana"


npsn_validator = RegexValidator(r"^\d{8}$", "NPSN harus terdiri dari 8 digit angka.")


class Sekolah(SoftDeleteModel):
    npsn = models.CharField("NPSN", max_length=8, unique=True, validators=[npsn_validator])
    nama = models.CharField("nama sekolah", max_length=200)
    jenjang = models.CharField(
        "jenjang", max_length=5, choices=Jenjang.choices, default=Jenjang.SMP
    )
    provinsi = models.ForeignKey(
        Provinsi, verbose_name="provinsi", on_delete=models.PROTECT, related_name="sekolah"
    )
    kabkota = models.ForeignKey(
        KabKota, verbose_name="kabupaten/kota", on_delete=models.PROTECT, related_name="sekolah"
    )
    status = models.CharField("status", max_length=10, choices=StatusSekolah.choices)
    pengusul = models.CharField("pengusul", max_length=10, choices=Pengusul.choices)
    mapel_kka = models.CharField("mapel KKA", max_length=12, choices=MapelKKA.choices)
    jumlah_guru = models.PositiveIntegerField("jumlah guru tetap", null=True, blank=True)
    # Kolom Excel yang belum punya kolom sendiri disimpan di sini (dipakai mesin impor).
    extra = models.JSONField("data tambahan", default=dict, blank=True, editable=False)

    history = HistoricalRecords()

    class Meta:
        ordering = ["provinsi__kode", "nama"]
        verbose_name = "sekolah"
        verbose_name_plural = "sekolah"

    def __str__(self):
        return f"{self.nama} ({self.npsn})"

    def clean(self):
        super().clean()
        if self.kabkota_id and self.provinsi_id and self.kabkota.provinsi_id != self.provinsi_id:
            raise ValidationError(
                {"kabkota": "Kabupaten/kota tidak berada di provinsi yang dipilih."}
            )
