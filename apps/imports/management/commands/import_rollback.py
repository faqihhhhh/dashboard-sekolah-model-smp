from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError

from apps.imports.models import ImportBatch
from apps.imports.rollback import rollback_batch


class Command(BaseCommand):
    help = "Membatalkan (rollback) satu batch impor."

    def add_arguments(self, parser):
        parser.add_argument("batch_id", type=int, help="ID batch impor yang akan dibatalkan")
        parser.add_argument(
            "--user",
            required=True,
            help="Email pengguna yang membatalkan batch",
        )
        parser.add_argument(
            "--reason",
            default="",
            help="Alasan pembatalan untuk riwayat",
        )

    def handle(self, *args, **options):
        batch_id = options["batch_id"]
        batch = ImportBatch.objects.filter(pk=batch_id).first()
        if not batch:
            raise CommandError(f"Batch impor #{batch_id} tidak ditemukan.")

        user_email = options["user"]
        User = get_user_model()
        user = User.objects.filter(email=user_email).first()
        if not user:
            raise CommandError(f"Pengguna dengan email '{user_email}' tidak ditemukan.")

        try:
            result = rollback_batch(
                batch=batch,
                user=user,
                reason=options["reason"] or None,
            )
        except (PermissionDenied, ValueError) as error:
            raise CommandError(f"Rollback gagal: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Rollback Batch #{batch_id} berhasil: "
                f"{result['soft_deleted']} data baru dihapus (soft-delete), "
                f"{result['reverted']} data diperbarui dikembalikan ke nilai sebelumnya."
            )
        )
