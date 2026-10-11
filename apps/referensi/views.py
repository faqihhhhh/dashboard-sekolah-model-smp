from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.permissions import SuperAdminRequiredMixin
from apps.core.mixins import FormPageMixin

from .forms import PeriodeForm
from .models import KabKota, Periode, Provinsi


class PeriodeListView(SuperAdminRequiredMixin, ListView):
    model = Periode
    template_name = "referensi/periode_list.html"
    context_object_name = "periode_list"


class PeriodeCreateView(SuperAdminRequiredMixin, FormPageMixin, SuccessMessageMixin, CreateView):
    model = Periode
    form_class = PeriodeForm
    template_name = "form.html"
    success_url = reverse_lazy("referensi:periode_list")
    success_message = "Periode berhasil dibuat."
    page_title = "Tambah periode"
    cancel_url_name = "referensi:periode_list"


class PeriodeUpdateView(SuperAdminRequiredMixin, FormPageMixin, SuccessMessageMixin, UpdateView):
    model = Periode
    form_class = PeriodeForm
    template_name = "form.html"
    success_url = reverse_lazy("referensi:periode_list")
    success_message = "Periode diperbarui."
    page_title = "Ubah periode"
    cancel_url_name = "referensi:periode_list"


class WilayahListView(SuperAdminRequiredMixin, ListView):
    """Daftar kabupaten/kota (baca-saja). Koreksi data dilakukan lewat /admin/."""

    model = KabKota
    template_name = "referensi/wilayah_list.html"
    context_object_name = "kabkota_list"
    paginate_by = 50

    def get_queryset(self):
        queryset = KabKota.objects.select_related("provinsi")
        query = self.request.GET.get("q", "").strip()
        provinsi = self.request.GET.get("provinsi", "")
        if query:
            queryset = queryset.filter(Q(nama__icontains=query) | Q(kode__icontains=query))
        if provinsi:
            queryset = queryset.filter(provinsi__kode=provinsi)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        context.update(
            provinsi_list=Provinsi.objects.all(),
            q=self.request.GET.get("q", "").strip(),
            selected_provinsi=self.request.GET.get("provinsi", ""),
            querystring=params.urlencode(),
            total_provinsi=Provinsi.objects.count(),
            total_kabkota=KabKota.objects.count(),
        )
        return context
