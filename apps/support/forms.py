from django import forms

from apps.core.forms import StyledFormMixin
from apps.sekolah.models import Sekolah

from .models import DokumenDukungan, JenisSurat


class DokumenDukunganForm(StyledFormMixin, forms.ModelForm):
    tautan_drive = forms.URLField(
        required=False,
        assume_scheme="https",
        label="Tautan Google Drive",
    )

    class Meta:
        model = DokumenDukungan
        fields = ("sekolah", "jenis", "berkas", "tautan_drive")
        widgets = {
            "berkas": forms.FileInput(attrs={"accept": ".pdf,application/pdf"}),
        }

    def __init__(self, *args, school=None, kind=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sekolah"].queryset = Sekolah.objects.select_related("provinsi", "kabkota")
        if school:
            self.fields["sekolah"].initial = school
            self.fields["sekolah"].disabled = True
        if kind:
            self.fields["jenis"].initial = kind
            self.fields["jenis"].disabled = True
        self.fields[
            "tautan_drive"
        ].help_text = "Gunakan tautan https yang dapat dibuka oleh pengguna berizin."
        self.fields[
            "berkas"
        ].help_text = "PDF maksimal 10 MB. Dokumen dilayani setelah pengguna masuk."

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and not cleaned.get("berkas") and not cleaned.get("tautan_drive"):
            # FileField mengembalikan berkas lama saat tidak diubah.
            if not self.instance.berkas:
                self.add_error("berkas", "Unggah PDF atau isi tautan Google Drive.")
        return cleaned

    def clean_jenis(self):
        kind = self.cleaned_data["jenis"]
        if kind not in JenisSurat.values:
            raise forms.ValidationError("Pilih jenis surat yang tersedia.")
        return kind
