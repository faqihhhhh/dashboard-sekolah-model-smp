from django import forms
from django.urls import reverse

from apps.core.forms import StyledFormMixin
from apps.referensi.models import KabKota

from .dataset import SEKOLAH
from .models import Sekolah


class SekolahForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Sekolah
        fields = SEKOLAH.form_fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pilihan kabupaten/kota mengikuti provinsi (514 pilihan sekaligus tidak praktis).
        raw = self.data.get("provinsi") if self.is_bound else self.instance.provinsi_id
        try:
            provinsi_id = int(raw)
        except (TypeError, ValueError):
            provinsi_id = None
        self.fields["kabkota"].queryset = (
            KabKota.objects.filter(provinsi_id=provinsi_id)
            if provinsi_id
            else KabKota.objects.none()
        )
        self.fields["provinsi"].empty_label = "Pilih provinsi"
        self.fields["kabkota"].empty_label = "Pilih kabupaten/kota"

        # HTMX: saat provinsi diganti, isi ulang daftar kabupaten/kota dari server.
        self.fields["provinsi"].widget.attrs.update(
            {
                "hx-get": reverse("sekolah:options_kabkota"),
                "hx-target": "#id_kabkota",
                "hx-trigger": "change",
            }
        )

    def clean_npsn(self):
        npsn = self.cleaned_data["npsn"].strip()
        existing = Sekolah.all_objects.filter(npsn=npsn).exclude(pk=self.instance.pk).first()
        if existing is not None:
            if existing.is_deleted:
                raise forms.ValidationError(
                    "NPSN ini ada pada data yang telah dihapus. Minta Super Admin memulihkannya."
                )
            raise forms.ValidationError("NPSN ini sudah terdaftar.")
        return npsn
