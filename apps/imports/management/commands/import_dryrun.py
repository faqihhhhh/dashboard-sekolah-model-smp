import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.registry import get_spec
from apps.imports.engine import DEFAULT_NULL_TOKENS, MappingConfig, run_dry_run
from apps.imports.readers import ReaderError, load_table


class Command(BaseCommand):
    help = "Menjalankan dry-run impor file data (tanpa menulis ke database)."

    def add_arguments(self, parser):
        parser.add_argument("dataset", help="Key dataset yang terdaftar di registry, mis. sekolah")
        parser.add_argument("file", help="Jalur file .xlsx atau .csv")
        parser.add_argument(
            "--mapping",
            required=True,
            help="Jalur file JSON konfigurasi pemetaan (MappingConfig)",
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

    def handle(self, *args, **options):
        dataset_key = options["dataset"]
        try:
            spec = get_spec(dataset_key)
        except KeyError as err:
            raise CommandError(f"Dataset '{dataset_key}' tidak ditemukan di registry.") from err

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
            self.stdout.write(self.style.ERROR("Pemetaan kolom bermasalah:"))
            for err in preview.mapping_errors:
                self.stdout.write(self.style.ERROR(f"  - {err}"))
            raise CommandError("Dry-run gagal karena pemetaan tidak valid.")

        counts = preview.counts()
        self.stdout.write(
            self.style.SUCCESS(
                f"Hasil dry-run: {counts['create']} baru, {counts['update']} perbarui, "
                f"{counts['unchanged']} tanpa perubahan, {counts['error']} error."
            )
        )

        for field_name, vals in preview.unknown_values.items():
            if vals:
                self.stdout.write(
                    self.style.WARNING(
                        f"Nilai tidak dikenal pada '{field_name}': {', '.join(sorted(vals))}"
                    )
                )

        if counts["error"] > 0:
            self.stdout.write(self.style.ERROR(f"Daftar masalah ({counts['error']} baris):"))
            for row_num, issue in preview.issues():
                self.stdout.write(
                    self.style.ERROR(f"  Baris {row_num}: [{issue.field or '-'}] {issue.message}")
                )
            raise CommandError(f"{counts['error']} baris mengalami error.")
