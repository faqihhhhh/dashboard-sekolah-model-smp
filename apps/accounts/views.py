from django.views.generic import ListView

from .models import Role, User
from .permissions import RoleRequiredMixin


class UserListView(RoleRequiredMixin, ListView):
    """Daftar pengguna (baca-saja untuk saat ini). Hanya Super Admin."""

    min_role = Role.SUPER_ADMIN
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    ordering = ["full_name"]
