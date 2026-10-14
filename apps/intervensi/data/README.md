# Referensi agregat kebutuhan intervensi

`agregat_baseline.csv` berisi nilai agregat yang disalin dari sheet `Kendala` dan
`Dukungan` pada `tests/fixtures/profil_kondisi_awal_baseline_sm_smp.xlsx`.
Setiap baris adalah satu proporsi untuk kombinasi jenis, kerangka, sasaran, dan
tingkat baseline; `jumlah_responden` berasal dari header kelompok pada workbook.

Bangun ulang CSV setelah workbook sumber berubah dengan menjalankan:

```sh
uv run python scripts/build_intervensi_reference.py
```

Jangan mengubah angka CSV secara manual. Data ini hanya menggambarkan kebutuhan
dan kendala agregat pada baseline; bukan rencana kegiatan, penyelenggara,
pelaksana, jadwal, status, atau realisasi intervensi.
