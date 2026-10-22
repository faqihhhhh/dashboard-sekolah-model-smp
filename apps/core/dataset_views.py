"""View generik untuk dataset yang terdaftar di registry.

Cara pakai: subclass dan isi `spec` (lihat apps/sekolah/views.py).
Guest boleh melihat daftar (kolom dibatasi); tambah/ubah/hapus/riwayat untuk Admin ke atas;
sampah dan pemulihan untuk Super Admin.
"""

from django import forms
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.accounts.models import Role
from apps.accounts.permissions import RoleRequiredMixin, SuperAdminRequiredMixin, has_role

from .forms import StyledFormMixin
from .history import build_history
from .mixins import FormPageMixin


class StyledModelForm(StyledFormMixin, forms.ModelForm):
    pass


class DatasetListView(ListView):
    spec = None
    template_name = "dataset/list.html"
    paginate_by = 25

    def get_queryset(self):
        spec, user = self.spec, self.request.user
        fields = spec.visible_fields(user)
        related = [f for f in fields if spec.model._meta.get_field(f).is_relation]
        queryset = spec.model.objects.select_related(*related)

        query = self.request.GET.get("q", "").strip()
        search_fields = spec.searchable_fields(user)
        if query and search_fields:
            condition = Q()
            for name in search_fields:
                condition |= Q(**{f"{name}__icontains": query})
            queryset = queryset.filter(condition)

        for name in spec.filterable_fields(user):
            values = (
                self.request.GET.getlist(name)
                if name == "provinsi"
                else [self.request.GET.get(name, "")]
            )
            valid_values = [value for value in values if value in dict(spec.filter_options(name))]
            if valid_values:  # nilai asing diabaikan
                if name == "provinsi":
                    queryset = queryset.filter(provinsi__in=valid_values)
                else:
                    queryset = queryset.filter(**{name: valid_values[0]})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        spec, user = self.spec, self.request.user
        fields = spec.visible_fields(user)
        can_edit = has_role(user, Role.ADMIN)

        rows = []
        for obj in context["page_obj"].object_list:
            row = {"cells": [spec.display(obj, f) for f in fields]}
            if can_edit:
                row["edit_url"] = spec.url("update", obj.pk)
                row["info_url"] = spec.url("info", obj.pk)
                row["delete_url"] = spec.url("delete", obj.pk)
            rows.append(row)

        params = self.request.GET.copy()
        params.pop("page", None)
        context.update(
            spec=spec,
            heading=f"Daftar {spec.label}",
            columns=[spec.field_label(f) for f in fields],
            rows=rows,
            filters=[
                {
                    "name": name,
                    "label": spec.field_label(name),
                    "options": spec.filter_options(name),
                    "selected": (
                        self.request.GET.getlist(name)
                        if name == "provinsi"
                        else self.request.GET.get(name, "")
                    ),
                }
                for name in spec.filterable_fields(user)
            ],
            q=self.request.GET.get("q", "").strip(),
            can_search=bool(spec.searchable_fields(user)),
            querystring=params.urlencode(),
            is_viewer=has_role(user, Role.VIEWER),
            can_edit=can_edit,
            create_url=spec.url("create") if can_edit else None,
            trash_url=spec.url("trash") if has_role(user, Role.SUPER_ADMIN) else None,
        )
        return context


class DatasetInfoView(RoleRequiredMixin, DetailView):
    """Rincian satu dataset untuk Admin ke atas."""

    min_role = Role.ADMIN
    spec = None
    template_name = "dataset/info.html"

    def get_queryset(self):
        return self.spec.model.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            spec=self.spec,
            fields=[
                {
                    "label": self.spec.field_label(name),
                    "value": self.spec.display(self.object, name),
                }
                for name in self.spec.list_fields
            ],
            back_url=self.spec.url("list"),
            edit_url=self.spec.url("update", self.object.pk),
        )
        return context


class DatasetFormMixin(RoleRequiredMixin, FormPageMixin, SuccessMessageMixin):
    min_role = Role.ADMIN
    spec = None
    form_class = None
    template_name = "form.html"

    @property
    def cancel_url_name(self):
        return f"{self.spec.url_namespace}:list"

    def get_success_url(self):
        return self.spec.url("list")

    def get_queryset(self):
        return self.spec.model.objects.all()

    def get_form_class(self):
        if self.form_class:
            return self.form_class
        return modelform_factory(
            self.spec.model, form=StyledModelForm, fields=self.spec.form_fields
        )


class DatasetCreateView(DatasetFormMixin, CreateView):
    success_message = "Data berhasil ditambahkan."

    def get_page_title(self):
        return f"Tambah {self.spec.label}"


class DatasetUpdateView(DatasetFormMixin, UpdateView):
    success_message = "Perubahan disimpan."

    def get_page_title(self):
        return f"Ubah {self.spec.label}"

    def form_valid(self, form):
        if not form.has_changed():  # hindari catatan riwayat kosong
            messages.info(self.request, "Tidak ada perubahan untuk disimpan.")
            return redirect(self.get_success_url())
        return super().form_valid(form)


class DatasetDeleteView(RoleRequiredMixin, DetailView):
    """GET = halaman konfirmasi, POST = hapus (soft delete)."""

    min_role = Role.ADMIN
    spec = None
    template_name = "dataset/confirm_delete.html"

    def get_queryset(self):
        return self.spec.model.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(spec=self.spec, cancel_url=self.spec.url("list"))
        return context

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.soft_delete(request.user)
        messages.success(request, "Data dihapus. Super Admin dapat memulihkannya.")
        return redirect(self.spec.url("list"))


class DatasetHistoryView(RoleRequiredMixin, DetailView):
    min_role = Role.ADMIN
    spec = None
    template_name = "dataset/history.html"

    def get_queryset(self):
        return self.spec.model._base_manager.all()  # riwayat data terhapus tetap bisa dilihat

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            spec=self.spec,
            entries=build_history(self.object),
            back_url=self.spec.url("list"),
        )
        return context


class DatasetTrashView(SuperAdminRequiredMixin, ListView):
    spec = None
    template_name = "dataset/trash.html"
    paginate_by = 25

    def get_queryset(self):
        return self.spec.model.all_objects.filter(deleted_at__isnull=False).order_by("-deleted_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = [
            {"obj": obj, "restore_url": self.spec.url("restore", obj.pk)}
            for obj in context["page_obj"].object_list
        ]
        context.update(spec=self.spec, rows=rows, back_url=self.spec.url("list"))
        return context


class DatasetRestoreView(SuperAdminRequiredMixin, View):
    http_method_names = ["post"]
    spec = None

    def post(self, request, pk):
        queryset = self.spec.model.all_objects.filter(deleted_at__isnull=False)
        obj = get_object_or_404(queryset, pk=pk)
        obj.restore()
        messages.success(request, f"{obj} dipulihkan.")
        return redirect(self.spec.url("trash"))
