from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User


class Command(BaseCommand):
    help = "Menampilkan nama, email, dan status akun Admin serta Super Admin."

    def handle(self, *args, **options):
        admins = User.objects.filter(role__in=[Role.ADMIN, Role.SUPER_ADMIN]).order_by(
            "role", "email"
        )

        if not admins.exists():
            self.stdout.write("Akun Admin atau Super Admin belum ada.")
            return

        for user in admins:
            status = "aktif" if user.is_active else "nonaktif"
            self.stdout.write(
                f"{user.get_role_display()} | {user.full_name} | {user.email} | {status}"
            )
