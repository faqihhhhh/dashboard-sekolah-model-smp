# Runbook operasional produksi

Panduan ini memakai Docker Compose produksi dari direktori proyek dan membutuhkan `.env.prod` yang sudah diisi. Jangan menyimpan file backup atau `.env.prod` ke Git.

## Membuat backup PostgreSQL

Jalankan backup saat aplikasi masih aktif:

```sh
make prod-backup
```

Perintah menghasilkan `backup-YYYY-MM-DD.sql.gz` di direktori proyek. Periksa file dan simpan salinannya di lokasi terpisah yang aksesnya dibatasi:

```sh
gzip -t backup-YYYY-MM-DD.sql.gz
ls -lh backup-YYYY-MM-DD.sql.gz
```

Backup berisi data pengguna dan sekolah. Batasi akses serta lindungi salinan yang dipindahkan ke penyimpanan lain.

## Memulihkan backup tanpa menimpa basis data aktif

Pulihkan dahulu ke basis data baru agar data aktif tetap utuh selama pemeriksaan. Ganti nama file dan nama basis data pemulihan pada contoh berikut agar unik:

```sh
BACKUP_FILE=backup-YYYY-MM-DD.sql.gz
RESTORE_DB=sekolah_model_pulih_20261015

gzip -t "$BACKUP_FILE"
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -e RESTORE_DB="$RESTORE_DB" db \
  sh -c 'createdb -U "$POSTGRES_USER" "$RESTORE_DB"'
gzip -dc "$BACKUP_FILE" | docker compose -f docker-compose.prod.yml \
  --env-file .env.prod exec -T -e RESTORE_DB="$RESTORE_DB" db sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$RESTORE_DB"'
```

Pastikan impor selesai tanpa error, lalu periksa tabel dan jumlah baris penting:

```sh
docker compose -f docker-compose.prod.yml --env-file .env.prod \
  exec -e RESTORE_DB="$RESTORE_DB" db sh -c \
  'psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -c "SELECT COUNT(*) FROM django_migrations;"'
```

Untuk mengalihkan aplikasi ke hasil pemulihan, ubah `POSTGRES_DB` dan nama database pada `DATABASE_URL` di `.env.prod` ke nilai `$RESTORE_DB`, lalu jalankan:

```sh
make prod-up
curl -fsS http://127.0.0.1:8080/healthz
```

Masuk ke aplikasi dan periksa data sebelum menghapus basis data lama. Jika situs memakai domain HTTPS, gunakan alamat situs tersebut untuk pemeriksaan health check. Pertahankan basis data lama sampai hasil pemulihan diterima.

## Batas verifikasi

Langkah pemulihan di atas belum pernah dijalankan terhadap Docker produksi pada sesi ini. Lakukan uji pemulihan berkala pada lingkungan terpisah sebelum mengandalkannya untuk pemulihan insiden.
