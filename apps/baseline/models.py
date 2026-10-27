from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import SoftDeleteModel, TimeStampedModel


class Kerangka(models.TextChoices):
    PM = "pm", "Pembelajaran Mendalam (PM)"
    KKA = "kka", "Koding dan Kecerdasan Artifisial (KKA)"


class LevelIndikator(models.TextChoices):
    L1 = "L1", "Level 1"
    L2 = "L2", "Level 2"
    L3 = "L3", "Level 3"


class RatingIndikator(models.TextChoices):
    PRA_BERKEMBANG = "pra_berkembang", "Pra-Berkembang"
    BERKEMBANG = "berkembang", "Berkembang"
    MAJU = "maju", "Maju"
    UNGGUL = "unggul", "Unggul"


class HasilBaseline(SoftDeleteModel):
    """Ringkasan hasil baseline satu sekolah pada satu Periode.

    Data profil disimpan sebagai JSON hingga nama field spesifik pada file sumber telah
    diverifikasi. Skor dan profil dicatat apa adanya; aplikasi tidak menghitungnya.
    """

    sekolah = models.ForeignKey(
        "sekolah.Sekolah",
        verbose_name="sekolah",
        on_delete=models.PROTECT,
        related_name="hasil_baseline",
    )
    periode = models.ForeignKey(
        "referensi.Periode",
        verbose_name="periode",
        on_delete=models.PROTECT,
        related_name="hasil_baseline",
    )
    skor_pm = models.DecimalField(
        "skor PM", max_digits=30, decimal_places=20, null=True, blank=True
    )
    profil_pm = models.CharField("profil PM", max_length=100, blank=True)
    skor_kka = models.DecimalField(
        "skor KKA", max_digits=30, decimal_places=20, null=True, blank=True
    )
    profil_kka = models.CharField("profil KKA", max_length=100, blank=True)
    profil_data = models.JSONField("data profil", default=dict, blank=True)
    import_batch = models.ForeignKey(
        "imports.ImportBatch",
        verbose_name="batch impor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hasil_baseline",
        editable=False,
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["sekolah__nama", "periode__tanggal_mulai"]
        constraints = [
            models.UniqueConstraint(
                fields=["sekolah", "periode"], name="uniq_hasil_baseline_sekolah_periode"
            )
        ]
        verbose_name = "hasil baseline"
        verbose_name_plural = "hasil baseline"

    def __str__(self):
        return f"Baseline {self.sekolah} · {self.periode}"


class KamusIndikator(TimeStampedModel):
    """Master kode dan panduan indikator PM/KKA."""

    kerangka = models.CharField("kerangka", max_length=10, choices=Kerangka.choices)
    level = models.CharField("level", max_length=2, choices=LevelIndikator.choices)
    kode = models.CharField("kode indikator", max_length=20)
    nama = models.CharField("nama indikator", max_length=200)
    deskripsi = models.TextField("panduan indikator", blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name="indikator induk",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    urutan = models.PositiveSmallIntegerField("urutan", default=0)
    aktif = models.BooleanField("aktif", default=True)

    class Meta:
        ordering = ["kerangka", "level", "urutan", "kode"]
        constraints = [
            models.UniqueConstraint(
                fields=["kerangka", "level", "kode"],
                name="uniq_kamus_indikator_kerangka_level_kode",
            )
        ]
        verbose_name = "indikator"
        verbose_name_plural = "kamus indikator"

    def __str__(self):
        return f"{self.get_kerangka_display()} {self.level} · {self.kode} — {self.nama}"

    def clean(self):
        super().clean()
        if not self.level or not self.parent_id:
            if self.level == LevelIndikator.L1 and self.parent_id:
                raise ValidationError({"parent": "Indikator Level 1 tidak memiliki induk."})
            if self.level in (LevelIndikator.L2, LevelIndikator.L3) and not self.parent_id:
                raise ValidationError({"parent": "Indikator Level 2 dan 3 harus memiliki induk."})
            return
        parent = self.parent
        expected_level = {
            LevelIndikator.L2: LevelIndikator.L1,
            LevelIndikator.L3: LevelIndikator.L2,
        }.get(self.level)
        if expected_level is None:
            raise ValidationError({"parent": "Level indikator tidak valid."})
        if parent.level != expected_level:
            raise ValidationError({"parent": f"Induk harus berada pada {expected_level}."})
        if parent.kerangka != self.kerangka:
            raise ValidationError({"parent": "Kerangka indikator dan induk harus sama."})


class PanduanRating(TimeStampedModel):
    """Uraian rubrik rating yang disediakan pada sheet MASTER file sumber baseline."""

    indikator = models.ForeignKey(
        KamusIndikator,
        verbose_name="indikator",
        on_delete=models.CASCADE,
        related_name="panduan_rating",
    )
    rating = models.CharField("rating", max_length=20, choices=RatingIndikator.choices)
    deskripsi = models.TextField("uraian rating")

    class Meta:
        ordering = ["indikator__kerangka", "indikator__urutan", "rating"]
        constraints = [
            models.UniqueConstraint(
                fields=["indikator", "rating"], name="uniq_panduan_rating_indikator_rating"
            )
        ]
        verbose_name = "panduan rating"
        verbose_name_plural = "panduan rating"

    def __str__(self):
        return f"{self.indikator.kode} · {self.get_rating_display()}"


class HasilIndikator(SoftDeleteModel):
    """Nilai rating satu indikator pada satu hasil baseline, tersimpan format panjang."""

    hasil_baseline = models.ForeignKey(
        HasilBaseline,
        verbose_name="hasil baseline",
        on_delete=models.CASCADE,
        related_name="hasil_indikator",
    )
    indikator = models.ForeignKey(
        KamusIndikator,
        verbose_name="indikator",
        on_delete=models.PROTECT,
        related_name="hasil",
    )
    rating = models.CharField(
        "rating",
        max_length=20,
        choices=RatingIndikator.choices,
        null=True,
        blank=True,
    )
    import_batch = models.ForeignKey(
        "imports.ImportBatch",
        verbose_name="batch impor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hasil_indikator",
        editable=False,
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["indikator__kerangka", "indikator__level", "indikator__urutan"]
        constraints = [
            models.UniqueConstraint(
                fields=["hasil_baseline", "indikator"],
                name="uniq_hasil_indikator_baseline_indikator",
            )
        ]
        verbose_name = "hasil indikator"
        verbose_name_plural = "hasil indikator"

    def clean(self):
        super().clean()
        if self.rating == "":
            self.rating = None
        if self.indikator_id and self.rating and self.rating not in RatingIndikator.values:
            raise ValidationError({"rating": "Pilih rating indikator yang tersedia."})

    def __str__(self):
        rating = self.get_rating_display() or "Tidak Terkategori"
        return f"{self.hasil_baseline} · {self.indikator.kode}: {rating}"
