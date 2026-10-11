from django.contrib.auth.mixins import AccessMixin

from .models import ROLE_RANK, Role


def has_role(user, min_role) -> bool:
    """True bila user login, aktif, dan perannya setara atau lebih tinggi dari min_role."""
    if user is None or not user.is_authenticated or not user.is_active:
        return False
    return ROLE_RANK[user.role] >= ROLE_RANK[min_role]


class RoleRequiredMixin(AccessMixin):
    """Mixin untuk class-based view.

    Belum login -> diarahkan ke halaman masuk. Sudah login tetapi perannya kurang -> 403.
    Pakai: class MyView(RoleRequiredMixin, View): min_role = Role.ADMIN
    """

    min_role = Role.VIEWER

    def dispatch(self, request, *args, **kwargs):
        if not has_role(request.user, self.min_role):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class SuperAdminRequiredMixin(RoleRequiredMixin):
    min_role = Role.SUPER_ADMIN
