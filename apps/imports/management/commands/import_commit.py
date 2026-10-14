import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role
from apps.accounts.permissions import has_role
from apps.core.registry import get_spec
from apps.imports.commit import CommitBlocked, commit_preview
from apps.imports.engine import DEFAULT_NULL_TOKENS, MappingConfig, run_dry_run
from apps.imports.readers import ReaderError, load_table


class Command(BaseCommand):
    help = "Melakukan commit impor data dari berkas .xlsx atau .csv ke database."

    def add_arguments(self, parser):
        parser.add_argument("dataset", help="Key dataset yang terdaftar di registry, mis. sekolah")
        parser.add_argument("file", help="Jalur file .xlsx atau .csv")
        parser.add_argument(
            "--mapping",
            required=True,
            help="Jalur file JSON konfigurasi pemetaan (MappingConfig)",
        )
        parser.add_argument(
            "--user",
            required=True,
            help="Email pengguna (Admin/Super Admin) yang melakukan impor",
        )
        parser.add_argument(
            "--sheet",
            default=None,
            help="Nama sheet yang akan dibaca (khusus file .xlsx)",
        )
        parser.add_argument(
            "--encoding",
            default=None,
            help="Encoding CSV yang dipilih: utf-8 atau windows-1252",
        )
        parser.add_argument(
            "--delimiter",
            default=None,
            help="Pemisah CSV yang dipilih: koma (,), titik koma (;), atau tab (\\t)",
        )
        parser.add_argument(
            "--skip-errors",
            action="store_true",
            default=False,
            help="Lewati baris yang bermasalah dan simpan baris yang valid",
        )
        parser.add_argument(
            "--reason",
            default="Impor data via CLI",
            help="Alasan perubahan untuk riwayat",
        )

    def handle(self, *args, **options):
        dataset_key = options["dataset"]
        try:
            spec = get_spec(dataset_key)
        except KeyError as err:
            raise CommandError(f"Dataset '{dataset_key}' tidak ditemukan di registry.") from err

        user_email = options["user"]
        User = get_user_model()
        user = User.objects.filter(email=user_email).first()
        if not user:
            raise CommandError(f"Pengguna dengan email '{user_email}' tidak ditemukan.")
        if not (has_role(user, Role.ADMIN) or has_role(user, Role.SUPER_ADMIN)):
            raise CommandError(
                f"Pengguna '{user_email}' tidak memiliki peran Admin atau Super Admin."
            )

        file_path = Path(options["file"])
        if not file_path.exists():
            raise CommandError(f"File data '{file_path}' tidak ditemukan.")

        mapping_path = Path(options["mapping"])
        if not mapping_path.exists():
            raise CommandError(f"File mapping '{mapping_path}' tidak ditemukan.")

        try:
            mapping_data = json.loads(mapping_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeError) as e:
            raise CommandError(f"File mapping tidak valid: {e}") from e

        if not isinstance(mapping_data, dict):
            raise CommandError("File mapping tidak valid: isi teratas harus berupa objek JSON.")

        try:
            mapping = MappingConfig(
                columns=mapping_data.get("columns", {}),
                header_rows=mapping_data.get("header_rows", (1,)),
                fill_right_rows=mapping_data.get("fill_right_rows", ()),
                first_data_row=mapping_data.get("first_data_row", 2),
                null_tokens=mapping_data.get("null_tokens", DEFAULT_NULL_TOKENS),
                value_maps=mapping_data.get("value_maps", {}),
            )
        except ValueError as error:
            raise CommandError(f"File mapping tidak valid: {error}") from error

        if file_path.suffix.lower() == ".csv":
            if options["encoding"] is None or options["delimiter"] is None:
                raise CommandError(
                    "Untuk file CSV, pilih --encoding dan --delimiter secara eksplisit."
                )

        try:
            table = load_table(
                file_path,
                sheet=options["sheet"],
                encoding=options["encoding"],
                delimiter=options["delimiter"],
            )
        except ReaderError as e:
            raise CommandError(f"Gagal membaca file: {e}") from e

        try:
            preview = run_dry_run(spec, table, mapping)
        except ReaderError as error:
            raise CommandError(f"Konfigurasi header tidak valid: {error}") from error

        if not preview.ok:
            for err in preview.mapping_errors:
                self.stdout.write(self.style.ERROR(f"  - {err}"))
            raise CommandError("Commit dibatalkan karena pemetaan tidak valid.")

        try:
            result = commit_preview(
                spec=spec,
                preview=preview,
                user=user,
                filename=file_path.name,
                sheet_name=options["sheet"] or "",
                mapping_config=mapping,
                reason=options["reason"],
                skip_errors=options["skip_errors"],
            )
        except CommitBlocked as e:
            raise CommandError(f"Commit gagal: {e}") from e

        self.stdout.write(
            self.style.SUCCESS(
                f"Commit berhasil (Batch #{result.batch.pk}): "
                f"{result.created} dibuat, {result.updated} diperbarui, "
                f"{result.unchanged} tanpa perubahan, {result.skipped} dilewati."
            )
        )
