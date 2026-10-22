from django.views.generic import TemplateView

from apps.accounts.models import Role
from apps.accounts.permissions import RoleRequiredMixin
from apps.core import dataset_views as dv
from apps.referensi.models import KabKota

from .dataset import SEKOLAH
from .forms import SekolahForm


class SekolahListView(dv.DatasetListView):
    spec = SEKOLAH


class SekolahInfoView(dv.DatasetInfoView):
    spec = SEKOLAH


class SekolahCreateView(dv.DatasetCreateView):
    spec = SEKOLAH
    form_class = SekolahForm


class SekolahUpdateView(dv.DatasetUpdateView):
    spec = SEKOLAH
    form_class = SekolahForm


class SekolahDeleteView(dv.DatasetDeleteView):
    spec = SEKOLAH


class SekolahHistoryView(dv.DatasetHistoryView):
    spec = SEKOLAH


class SekolahTrashView(dv.DatasetTrashView):
    spec = SEKOLAH


class SekolahRestoreView(dv.DatasetRestoreView):
    spec = SEKOLAH


class KabKotaOptionsView(RoleRequiredMixin, TemplateView):
    """Potongan HTML <option> untuk HTMX: kabupaten/kota milik provinsi terpilih."""

    min_role = Role.ADMIN
    template_name = "sekolah/_kabkota_options.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            provinsi_id = int(self.request.GET.get("provinsi", ""))
        except ValueError:
            provinsi_id = None
        context["kabkota_list"] = (
            KabKota.objects.filter(provinsi_id=provinsi_id)
            if provinsi_id
            else KabKota.objects.none()
        )
        return context
