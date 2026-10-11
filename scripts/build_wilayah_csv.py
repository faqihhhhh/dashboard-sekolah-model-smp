"""Membuat apps/referensi/data/wilayah.csv dari dataset kode wilayah Kemendagri.

Sumber : https://github.com/cahyadsn/wilayah (lisensi MIT), file db/wilayah.sql,
         sesuai Kepmendagri No. 300.2.2-2430 Tahun 2025.
Hanya level provinsi dan kabupaten/kota yang disimpan (kecamatan dan desa dibuang).

Jalankan: uv run python scripts/build_wilayah_csv.py
"""

import csv
import re
import urllib.request
from pathlib import Path

# Di-pin ke commit tertentu agar hasilnya selalu sama. Ganti SHA ini hanya bila
# ingin memperbarui data wilayah, lalu commit CSV hasilnya.
COMMIT = "7586f4278ecbcbabd4b65f8d594913e9d256a29a"
URL = f"https://raw.githubusercontent.com/cahyadsn/wilayah/{COMMIT}/db/wilayah.sql"
OUT = Path(__file__).resolve().parent.parent / "apps" / "referensi" / "data" / "wilayah.csv"

ROW = re.compile(r"\('([0-9.]+)','([^']*)'\)")


def main() -> None:
    print(f"Mengunduh {URL}")
    with urllib.request.urlopen(URL, timeout=120) as response:
        sql = response.read().decode("utf-8", errors="replace")

    rows = []
    for kode, nama in ROW.findall(sql):
        if kode.count(".") <= 1:  # "11" = provinsi, "11.01" = kabupaten/kota
            rows.append((kode, " ".join(nama.split())))
    rows.sort(key=lambda r: r[0])

    n_prov = sum(1 for kode, _ in rows if "." not in kode)
    n_kab = len(rows) - n_prov
    if n_prov != 38 or n_kab < 500:
        raise SystemExit(f"Jumlah tidak wajar: {n_prov} provinsi, {n_kab} kab/kota. Dibatalkan.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["kode", "nama"])
        writer.writerows(rows)

    print(f"Selesai: {n_prov} provinsi, {n_kab} kabupaten/kota -> {OUT}")


if __name__ == "__main__":
    main()
