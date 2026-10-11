import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.referensi.models import (
    AliasKabKota,
    AliasProvinsi,
    JenisKabKota,
    KabKota,
    Provinsi,
)

DEFAULT_CSV = Path(__file__).resolve().parents[2] / "data" / "wilayah.csv"

# Penulisan lain yang sudah diketahui muncul pada data (kunci = kode Kemendagri).
ALIAS_PROVINSI = {
    "19": ["Bangka Belitung", "Babel"],
    "31": ["DKI Jakarta", "Jakarta"],
    "34": ["D.I. Yogyakarta", "DI Yogyakarta", "DIY"],
    "52": ["NTB"],
    "53": ["NTT"],
}
ALIAS_KABKOTA = {
    "31.01": ["Kepulauan Seribu"],
    "31.71": ["Jakarta Pusat"],
    "31.72": ["Jakarta Utara"],
    "31.73": ["Jakarta Barat"],
    "31.74": ["Jakarta Selatan"],
    "31.75": ["Jakarta Timur"],
    "33.71": ["Kota Magelan"],  # salah ketik pada file baseline
    "65.71": ["Kota Tarakan Barat"],  # salah ketik pada file baseline
    "73.71": ["Kota Makasar"],  # salah ketik pada file baseline
}


class Command(BaseCommand):
    help = "Mengisi atau memperbarui provinsi dan kabupaten/kota dari CSV. Aman dijalankan ulang."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_CSV), help="Path CSV (kode,nama).")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(
                f"{path} tidak ada. Jalankan dulu: uv run python scripts/build_wilayah_csv.py"
            )

        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        provinsi_baru = kabkota_baru = 0
        for row in rows:  # provinsi lebih dulu (kode tanpa titik)
            if "." not in row["kode"]:
                _, created = Provinsi.objects.update_or_create(
                    kode=row["kode"], defaults={"nama": row["nama"]}
                )
                provinsi_baru += created

        provinsi_by_kode = {p.kode: p for p in Provinsi.objects.all()}
        for row in rows:
            if "." not in row["kode"]:
                continue
            nama = row["nama"]
            jenis = JenisKabKota.KOTA if nama.lower().startswith("kota") else JenisKabKota.KABUPATEN
            _, created = KabKota.objects.update_or_create(
                kode=row["kode"],
                defaults={
                    "provinsi": provinsi_by_kode[row["kode"].split(".")[0]],
                    "jenis": jenis,
                    "nama": nama,
                },
            )
            kabkota_baru += created

        alias_baru = self._seed_alias()
        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai. Provinsi: {Provinsi.objects.count()} (baru {provinsi_baru}), "
                f"kab/kota: {KabKota.objects.count()} (baru {kabkota_baru}), "
                f"alias baru: {alias_baru}."
            )
        )

    def _seed_alias(self) -> int:
        baru = 0
        for kode, names in ALIAS_PROVINSI.items():
            target = Provinsi.objects.filter(kode=kode).first()
            for alias in names if target else []:
                if not AliasProvinsi.objects.filter(alias__iexact=alias).exists():
                    AliasProvinsi.objects.create(provinsi=target, alias=alias)
                    baru += 1
        for kode, names in ALIAS_KABKOTA.items():
            target = KabKota.objects.filter(kode=kode).first()
            for alias in names if target else []:
                if not AliasKabKota.objects.filter(alias__iexact=alias).exists():
                    AliasKabKota.objects.create(kabkota=target, alias=alias)
                    baru += 1
        return baru
