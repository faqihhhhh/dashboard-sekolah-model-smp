# Dasbor Monitoring Sekolah Model SMP

Aplikasi Django untuk memantau program Sekolah Model SMP: ringkasan sekolah, baseline, surat dukungan, referensi wilayah, dan impor data Excel/CSV.

## Menjalankan untuk pengembangan

Kebutuhan: Python 3.12, [uv](https://docs.astral.sh/uv/), dan Docker Compose.

```sh
uv sync --locked --all-groups
cp .env.example .env
```

Ubah `SECRET_KEY` di `.env`, kemudian jalankan PostgreSQL dan siapkan data awal:

```sh
make up
make migrate
make seed
make superuser
make dev
```

Buka <http://localhost:8000>. `make seed` mengisi referensi wilayah serta 56 entri codebook dan 136 rubrik baseline; perintahnya aman dijalankan ulang. `make dev` membangun CSS, menerapkan migrasi, lalu menjalankan Django. Untuk membuat 60 sekolah fiktif saat `DEBUG=True`, jalankan `make seed-demo`; hapus semuanya dengan `make demo-hapus` sebelum mengimpor data asli.

## Pemeriksaan

```sh
make fmt
make check
```

GitHub Actions menjalankan Django check, lint, dan tes terhadap PostgreSQL 17 pada setiap push dan pull request.

## Operasional produksi

Salin `.env.prod.example` ke `.env.prod`, isi rahasia produksi, lalu gunakan `make prod-up`. Prosedur backup dan pemulihan ada di [docs/operasional.md](docs/operasional.md). Jangan commit `.env`, `.env.prod`, file backup, atau data produksi.

## Panduan proyek

Arsitektur, aturan hak akses, kebijakan impor, dan roadmap ada di [AGENT.md](AGENT.md). Fitur Kurasi dan Rencana Tindak Lanjut serta pencatatan kegiatan Intervensi menunggu spesifikasi pemilik.
