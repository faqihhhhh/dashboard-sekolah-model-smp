from django import forms

from apps.core.forms import StyledFormMixin

from .models import Periode


class PeriodeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Periode
        fields = ["nama", "jenis", "tanggal_mulai", "tanggal_selesai"]
        widgets = {
            "tanggal_mulai": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "tanggal_selesai": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {
            "nama": "Contoh: Baseline 2026, Monitoring 1.",
            "tanggal_mulai": "Dipakai sebagai posisi periode pada sumbu waktu chart.",
        }

    def clean(self):
        cleaned = super().clean()
        mulai, selesai = cleaned.get("tanggal_mulai"), cleaned.get("tanggal_selesai")
        if mulai and selesai and selesai < mulai:
            self.add_error("tanggal_selesai", "Tanggal selesai tidak boleh sebelum tanggal mulai.")
        return cleaned
