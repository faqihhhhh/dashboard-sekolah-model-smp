from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import SoftDeleteModel
from apps.sekolah.models import Sekolah


class KerangkaPraktik(models.TextChoices):
    PM = "pm", "Pembelajaran Mendalam (PM)"
    KKA = "kka", "Koding & Kecerdasan Artifisial (KKA)"
    PM_KKA = "pm_kka", "PM & KKA"


class VideoPraktik(SoftDeleteModel):
    sekolah = models.ForeignKey(
        Sekolah,
        verbose_name="sekolah",
        on_delete=models.PROTECT,
        related_name="video_praktik",
    )
    judul = models.CharField("judul video", max_length=180)
    kerangka = models.CharField("bidang praktik", max_length=10, choices=KerangkaPraktik.choices)
    deskripsi = models.TextField("deskripsi", blank=True, max_length=2000)
    tautan = models.URLField(
        "tautan video",
        validators=[URLValidator(schemes=["https"])],
        help_text="Tautan YouTube, Google Drive, Vimeo, atau halaman video HTTPS lainnya.",
    )
    dipublikasikan = models.BooleanField(
        "ditampilkan kepada pengguna",
        default=False,
        help_text="Hanya video yang disetujui Admin yang tampil.",
    )
    history = HistoricalRecords()

    class Meta:
        ordering = ["-updated_at", "judul"]
        verbose_name = "video praktik baik"
        verbose_name_plural = "video praktik baik"

    def clean(self):
        super().clean()
        if not self.tautan:
            return
        host = (urlsplit(self.tautan).hostname or "").lower().rstrip(".")
        parsed = urlsplit(self.tautan)
        if not host or "." not in host or parsed.username or parsed.password:
            raise ValidationError({"tautan": "Masukkan tautan video HTTPS yang valid."})

    @property
    def penyedia(self):
        host = (urlsplit(self.tautan).hostname or "").lower().removeprefix("www.")
        if host == "youtu.be" or host.endswith(".youtube.com") or host == "youtube.com":
            return "YouTube"
        if host == "drive.google.com" or host.endswith(".drive.google.com"):
            return "Google Drive"
        if host == "vimeo.com" or host.endswith(".vimeo.com"):
            return "Vimeo"
        return "Tautan video"

    @property
    def embed_url(self):
        """Hanya buat iframe untuk host yang dikenal; tautan lain dibuka di tab baru."""
        parsed = urlsplit(self.tautan)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if host == "youtu.be":
            video_id = parsed.path.strip("/").split("/")[0]
        elif host == "youtube.com" or host.endswith(".youtube.com"):
            path_parts = parsed.path.strip("/").split("/")
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif len(path_parts) == 2 and path_parts[0] in {"embed", "shorts", "live"}:
                video_id = path_parts[1]
            else:
                video_id = ""
        elif host in {"drive.google.com", "docs.google.com"}:
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 3 and path_parts[0] == "file" and path_parts[1] == "d":
                file_id = path_parts[2]
            else:
                file_id = parse_qs(parsed.query).get("id", [""])[0]
            return f"https://drive.google.com/file/d/{file_id}/preview" if file_id else ""
        elif host == "player.vimeo.com":
            return self.tautan
        elif host == "vimeo.com":
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://player.vimeo.com/video/{video_id}" if video_id.isdigit() else ""
        else:
            return ""
        if not video_id or not all(char.isalnum() or char in "-_" for char in video_id):
            return ""
        return f"https://www.youtube-nocookie.com/embed/{video_id}"

    def __str__(self):
        return f"{self.judul} — {self.sekolah}"
