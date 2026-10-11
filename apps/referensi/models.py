from django.db import models
from django.db.models.functions import Lower


class Provinsi(models.Model):
    kode = models.CharField("kode", max_length=2, unique=True)  # kode Kemendagri, mis. "32"
    nama = models.CharField("nama", max_length=100)

    class Meta:
        ordering = ["kode"]
        verbose_name = "provinsi"
        verbose_name_plural = "provinsi"

    def __str__(self):
        return self.nama


class JenisKabKota(models.TextChoices):
    KABUPATEN = "kabupaten", "Kabupaten"
    KOTA = "kota", "Kota"


class KabKota(models.Model):
    provinsi = models.ForeignKey(Provinsi, on_delete=models.PROTECT, related_name="kabkota")
    kode = models.CharField("kode", max_length=5, unique=True)  # mis. "32.73"
    jenis = models.CharField("jenis", max_length=10, choices=JenisKabKota.choices)
    nama = models.CharField("nama resmi", max_length=120)  # mis. "Kota Bandung"

    class Meta:
        ordering = ["kode"]
        verbose_name = "kabupaten/kota"
        verbose_name_plural = "kabupaten/kota"

    def __str__(self):
        return self.nama


class AliasProvinsi(models.Model):
    """Penulisan lain untuk sebuah provinsi (dipakai saat impor untuk mencocokkan nama)."""

    provinsi = models.ForeignKey(Provinsi, on_delete=models.CASCADE, related_name="alias")
    alias = models.CharField("alias", max_length=150)

    class Meta:
        verbose_name = "alias provinsi"
        verbose_name_plural = "alias provinsi"
        constraints = [
            models.UniqueConstraint(Lower("alias"), name="uniq_alias_provinsi_lower"),
        ]

    def __str__(self):
        return f"{self.alias} -> {self.provinsi}"


class AliasKabKota(models.Model):
    """Penulisan lain untuk sebuah kabupaten/kota (mis. salah ketik yang sering muncul)."""

    kabkota = models.ForeignKey(KabKota, on_delete=models.CASCADE, related_name="alias")
    alias = models.CharField("alias", max_length=150)

    class Meta:
        verbose_name = "alias kabupaten/kota"
        verbose_name_plural = "alias kabupaten/kota"
        constraints = [
            models.UniqueConstraint(Lower("alias"), name="uniq_alias_kabkota_lower"),
        ]

    def __str__(self):
        return f"{self.alias} -> {self.kabkota}"


class JenisPeriode(models.TextChoices):
    BASELINE = "baseline", "Baseline"
    MONITORING = "monitoring", "Monitoring"
    ENDLINE = "endline", "Endline"


class Periode(models.Model):
    """Periode pengukuran. Menjadi sumbu waktu untuk chart perkembangan."""

    nama = models.CharField("nama", max_length=100, unique=True)
    jenis = models.CharField(
        "jenis", max_length=12, choices=JenisPeriode.choices, default=JenisPeriode.BASELINE
    )
    tanggal_mulai = models.DateField("tanggal mulai")
    tanggal_selesai = models.DateField("tanggal selesai", null=True, blank=True)

    class Meta:
        ordering = ["tanggal_mulai", "id"]
        verbose_name = "periode"
        verbose_name_plural = "periode"

    def __str__(self):
        return self.nama
