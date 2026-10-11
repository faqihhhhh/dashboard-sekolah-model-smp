from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.functional import cached_property
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.core.mixins import FormPageMixin

from .forms import AdminSetPasswordForm, UserCreateForm, UserUpdateForm
from .models import User
from .permissions import SuperAdminRequiredMixin


class UserListView(SuperAdminRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    ordering = ["full_name"]


class UserCreateView(SuperAdminRequiredMixin, FormPageMixin, SuccessMessageMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "form.html"
    success_url = reverse_lazy("accounts:user_list")
    success_message = "Pengguna berhasil dibuat."
    page_title = "Tambah pengguna"
    submit_label = "Buat pengguna"
    cancel_url_name = "accounts:user_list"


class UserUpdateView(SuperAdminRequiredMixin, FormPageMixin, SuccessMessageMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "form.html"
    success_url = reverse_lazy("accounts:user_list")
    success_message = "Perubahan pengguna disimpan."
    page_title = "Ubah pengguna"
    cancel_url_name = "accounts:user_list"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["acting_user"] = self.request.user
        return kwargs


class UserPasswordView(SuperAdminRequiredMixin, FormPageMixin, FormView):
    form_class = AdminSetPasswordForm
    template_name = "form.html"
    success_url = reverse_lazy("accounts:user_list")
    submit_label = "Simpan kata sandi"
    cancel_url_name = "accounts:user_list"

    @cached_property
    def target(self):
        return get_object_or_404(User, pk=self.kwargs["pk"])

    def get_page_title(self):
        return f"Atur kata sandi: {self.target.full_name}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target
        return kwargs

    def form_valid(self, form):
        form.save()
        if self.target.pk == self.request.user.pk:
            update_session_auth_hash(self.request, self.target)  # agar tidak ikut logout
        messages.success(self.request, "Kata sandi berhasil diubah.")
        return super().form_valid(form)
