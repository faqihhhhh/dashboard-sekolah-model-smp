import csv
from decimal import Decimal
from pathlib import Path

from django.conf import settings

DATA_FILE = Path(settings.BASE_DIR) / "apps/intervensi/data/agregat_baseline.csv"
FRAMEWORKS = {"pm": "Pembelajaran Mendalam (PM)", "kka": "Koding & Kecerdasan Artifisial (KKA)"}
TARGETS = {"kepala_sekolah": "Kepala Sekolah", "guru": "Guru"}
KINDS = {"kendala": "Kendala", "dukungan": "Dukungan yang dibutuhkan"}


def intervention_data(framework, target):
    grouped = {"kendala": {}, "dukungan": {}}
    with DATA_FILE.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["kerangka"] != framework or row["sasaran"] != target:
                continue
            category = grouped[row["jenis"]].setdefault(
                row["urutan"], {"name": row["kategori"], "values": []}
            )
            proportion = Decimal(row["proporsi"])
            percent = proportion * 100
            percent_label = f"{percent:.2f}".rstrip("0").rstrip(".")
            category["values"].append(
                {
                    "label": row["tingkat_label"],
                    "sample_size": int(row["jumlah_responden"]),
                    "percent": percent_label,
                    "bar_width": percent_label,
                }
            )
    return {
        kind: [grouped[kind][key] for key in sorted(grouped[kind], key=int)] for kind in grouped
    }
