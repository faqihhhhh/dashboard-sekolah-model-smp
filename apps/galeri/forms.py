from urllib.parse import urlsplit

from django import forms

from apps.core.forms import StyledFormMixin
from apps.sekolah.models import Sekolah

from .models import VideoPraktik


class VideoPraktikForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = VideoPraktik
        fields = ("sekolah", "judul", "kerangka", "deskripsi", "tautan", "dipublikasikan")
        widgets = {
            "deskripsi": forms.Textarea(attrs={"rows": 4}),
            "tautan": forms.URLInput(attrs={"placeholder": "https://..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sekolah"].queryset = Sekolah.objects.select_related("provinsi", "kabkota")
        self.fields[
            "dipublikasikan"
        ].help_text = "Jika dicentang, video dapat dilihat semua pengguna yang sudah masuk."

    def clean_tautan(self):
        url = self.cleaned_data["tautan"]
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if not host or "." not in host or parsed.username or parsed.password:
            raise forms.ValidationError("Masukkan tautan video HTTPS yang valid.")
        return url
