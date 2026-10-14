import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.baseline.models import KamusIndikator, PanduanRating

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Command(BaseCommand):
    help = "Mengisi kamus indikator dan panduan rating baseline; aman dijalankan ulang."

    def add_arguments(self, parser):
        parser.add_argument("--indikator", default=str(DATA_DIR / "indikator.csv"))
        parser.add_argument("--panduan", default=str(DATA_DIR / "panduan_rating.csv"))

    @transaction.atomic
    def handle(self, *args, **options):
        indicator_path = Path(options["indikator"])
        guide_path = Path(options["panduan"])
        for path in (indicator_path, guide_path):
            if not path.is_file():
                raise CommandError(f"Berkas referensi tidak ditemukan: {path}")

        with indicator_path.open(encoding="utf-8-sig", newline="") as source:
            indicators = list(csv.DictReader(source))
        with guide_path.open(encoding="utf-8-sig", newline="") as source:
            guides = list(csv.DictReader(source))
        if not indicators or not guides:
            raise CommandError("Berkas kamus atau panduan rating kosong.")

        by_key = {}
        created_count = updated_count = 0
        # CSV dihasilkan berurutan dari induk ke anak, sehingga parent sudah tersedia.
        for row in indicators:
            key = (row["kerangka"], row["level"], row["kode"])
            parent = None
            if row["parent_level"]:
                parent_key = (row["kerangka"], row["parent_level"], row["parent_code"])
                parent = (
                    by_key.get(parent_key)
                    or KamusIndikator.objects.filter(
                        kerangka=parent_key[0], level=parent_key[1], kode=parent_key[2]
                    ).first()
                )
                if parent is None:
                    raise CommandError(f"Indikator induk tidak ditemukan untuk {key}.")
            indicator, created = KamusIndikator.objects.update_or_create(
                kerangka=row["kerangka"],
                level=row["level"],
                kode=row["kode"],
                defaults={
                    "nama": row["nama"],
                    "parent": parent,
                    "urutan": int(row["urutan"]),
                    "aktif": True,
                },
            )
            by_key[key] = indicator
            created_count += created
            updated_count += not created

        guide_count = 0
        for row in guides:
            indicator = by_key.get((row["kerangka"], "L3", row["kode_indikator"]))
            if indicator is None:
                raise CommandError(
                    "Panduan merujuk indikator yang tidak ada: "
                    f"{row['kerangka']} {row['kode_indikator']}."
                )
            PanduanRating.objects.update_or_create(
                indikator=indicator,
                rating=row["rating"],
                defaults={"deskripsi": row["deskripsi"]},
            )
            guide_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai. Kamus: {len(indicators)} "
                f"({created_count} baru, {updated_count} diperbarui); "
                f"panduan rating diproses: {guide_count}."
            )
        )
