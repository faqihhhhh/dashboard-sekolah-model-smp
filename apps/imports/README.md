# Mesin impor (tahap 2.1)

`import_dryrun` membaca dan memvalidasi file tanpa mengubah database. Kolom sumber harus dipetakan manual ke field dataset melalui file JSON. Kolom yang tidak tercantum di `columns` tidak dipakai.

Contoh `pemetaan-sekolah.json`:

```json
{
  "columns": {
    "NPSN Sekolah": "npsn",
    "Nama Sekolah": "nama",
    "Kabupaten/Kota": "kabkota",
    "Status": "status",
    "Pengusul": "pengusul",
    "Mapel KKA": "mapel_kka",
    "Jumlah Guru": "jumlah_guru"
  },
  "header_rows": [1],
  "first_data_row": 2,
  "null_tokens": ["#N/A"],
  "value_maps": {
    "pengusul": {"Pemda": "dinas"}
  }
}
```

Nilai di sisi kiri `columns` harus sama persis dengan header hasil pembacaan. Header bertingkat digabung memakai ` | `; untuk sel grup yang digabung, sebutkan nomor baris yang perlu diisi ke kanan di `fill_right_rows`. `value_maps` adalah keputusan pemetaan alias yang ditulis Admin; nilai lain yang tidak dikenal dilaporkan, tidak ditebak.

Jalankan:

```sh
uv run python manage.py import_dryrun sekolah data.xlsx --sheet Data --mapping pemetaan-sekolah.json
uv run python manage.py import_dryrun sekolah data.csv --mapping pemetaan-sekolah.json --encoding utf-8 --delimiter ';'
```

Untuk CSV, pilihan encoding dan delimiter wajib ditulis. Untuk XLSX dengan beberapa sheet, `--sheet` wajib ditulis. Dry-run hanya menampilkan ringkasan aksi, nilai yang belum dikenal, dan error per baris; penyimpanan data menyusul di tahap berikutnya.
