import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.referensi.models import KabKota
from apps.sekolah.models import MapelKKA, Pengusul, Sekolah, StatusSekolah


class Command(BaseCommand):
    help = "Membuat sekolah FIKTIF untuk uji tampilan (hanya saat DEBUG). --hapus menghapusnya."

    def add_arguments(self, parser):
        parser.add_argument("--jumlah", type=int, default=60)
        parser.add_argument("--hapus", action="store_true", help="Hapus semua data demo.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Hanya boleh dijalankan saat DEBUG=True.")

        if options["hapus"]:
            Sekolah.history.filter(extra__demo=True).delete()
            deleted, _ = Sekolah.all_objects.filter(extra__demo=True).delete()
            self.stdout.write(self.style.SUCCESS(f"{deleted} data demo dihapus."))
            return

        kabkota = list(KabKota.objects.select_related("provinsi"))
        if not kabkota:
            raise CommandError("Data wilayah kosong. Jalankan dulu: make seed")

        rng = random.Random(2026)  # deterministik: hasil sama setiap dijalankan
        for i in range(1, options["jumlah"] + 1):
            lokasi = rng.choice(kabkota)
            Sekolah.all_objects.update_or_create(
                npsn=f"99{i:06d}",  # awalan 99 agar tidak bentrok dengan NPSN asli
                defaults={
                    "nama": f"SMP Contoh {i:03d} - {lokasi.nama}",
                    "provinsi": lokasi.provinsi,
                    "kabkota": lokasi,
                    "status": rng.choice(StatusSekolah.values),
                    "pengusul": rng.choice(Pengusul.values),
                    "mapel_kka": rng.choice(MapelKKA.values),
                    "jumlah_guru": rng.randint(8, 80),
                    "extra": {"demo": True},
                },
            )
        self.stdout.write(self.style.SUCCESS(f"{options['jumlah']} sekolah demo siap."))
