# AGENT.md — Dasbor Monitoring Sekolah Model SMP

> Panduan untuk AI/pengembang mana pun yang bekerja di repo ini. **Baca seluruh file sebelum mengubah kode.**
> Saat menyelesaikan sebuah langkah, perbarui bagian [10. Status dan peta jalan](#10-status-dan-peta-jalan).
> Bahasa komunikasi dengan pemilik dan semua teks antarmuka: **Indonesia**.

## 1. Apa ini

Aplikasi web untuk memantau program **Sekolah Model SMP** (Pembelajaran Mendalam/PM dan Koding & Kecerdasan Artifisial/KKA).
Tampilannya mengacu pada dasbor program yang sama untuk SMA, tetapi data **tidak diinput satu per satu**: Admin memasukkannya lewat
**impor Excel/CSV** (pemetaan kolom dibuat manual oleh Admin, tidak ditebak sistem) atau lewat **formulir**. Semua data bisa diedit,
dan data yang punya dimensi waktu mendapat **chart perkembangan**.

Modul: Beranda (KPI, peta provinsi, daftar sekolah) · Surat Dukungan · Baseline Sekolah · Intervensi (Direktorat SMP, BBPMP/BPMP,
Dinas Pendidikan) · Kurasi dan Rencana Tindak Lanjut (**ditunda**, belum ada spesifikasi).
Skala: ratusan sekolah, puluhan pengguna. Hosting belum ditentukan. Tidak ada persyaratan kepatuhan khusus.

## 2. Aturan emas (jangan dilanggar tanpa persetujuan pemilik)

1. **Hak akses dipaksakan di server.** Guest = pengunjung anonim. Kolom/data terbatas tidak boleh ikut terkirim ke Guest (HTML maupun JSON);
   menyembunyikan di UI saja tidak cukup. Setiap fitur wajib punya tes matriks peran dan tes bahwa Guest tidak menerima data terbatas.
2. **Impor tidak menebak.** Admin memetakan kolom file → field secara manual. Nilai tak dikenal dilaporkan dan Admin yang memilih nilai bakunya
   (disimpan sebagai alias). Satu-satunya kanonisasi otomatis yang boleh: huruf besar/kecil, tanda baca, spasi, awalan Kab./Kota/Adm.
   Bila hasil **tidak unik atau tidak ditemukan → jangan ditebak**.
3. **Skor dan profil tidak dihitung sistem.** Dicatat apa adanya dari file/input manual. Agregat tampilan (jumlah, rata-rata, persentase)
   tetap dihitung.
4. **Soft delete + riwayat perubahan** untuk semua dataset. Hapus permanen hanya lewat `/admin/` oleh Super Admin.
5. **Satu sumber kebenaran per dataset:** model Django + `DatasetSpec`. Jangan menyalin daftar field ke banyak tempat.
6. **Tanpa SPA/React dan tanpa CDN.** Frontend dirender server (template Django) + HTMX + Alpine.js, semua JS/CSS disimpan lokal.
7. **Jangan menimpa data lama dengan sel kosong** saat impor; field yang tidak dipetakan tidak disentuh saat pembaruan.
8. **Jangan mengarang spesifikasi** untuk Kurasi, Rencana Tindak Lanjut, atau format file intervensi/surat dukungan. Tanyakan pemilik.
9. **Setiap perubahan:** tes ditulis, `make fmt` lalu `make check` hijau, migrasi ikut di-commit. Jangan meninggalkan tes gagal.
10. **Lapor jujur** apa yang belum teruji (terutama Docker dan tampilan di browser).

## 3. Stack (versi di-pin; jangan diganti tanpa alasan)

Python 3.12 · Django 5.2 LTS · PostgreSQL 17 (18 mengubah path volume image) · django-simple-history 3.13.0 · argon2-cffi ·
django-environ · gunicorn · whitenoise · **HTMX 2.0.11** · **Alpine.js 3.17.4** · **Tailwind CSS 4.3.3** (CLI mandiri, tanpa Node.js) ·
uv · ruff · pytest-django · **openpyxl 3.1.5** (pembaca impor XLSX) · Docker Compose · Caddy 2.
Belum terpasang, akan dibutuhkan: **ECharts** (chart dan peta; simpan lokal di `static/vendor/`).

## 4. Perintah (Makefile)

Resep Makefile diawali `>` (bukan TAB) lewat `.RECIPEPREFIX`. Pengembangan di Ubuntu/WSL2; repo harus di filesystem Linux (`~/`), bukan `/mnt/c`.

```
make up          # PostgreSQL dev via Docker
make migrate     # terapkan migrasi            | make makemigrations
make seed        # 38 provinsi, 514 kab/kota, alias awal
make superuser   # buat Super Admin
make seed-demo   # 60 sekolah FIKTIF (hanya DEBUG); hapus: make demo-hapus  (WAJIB sebelum impor data asli)
make dev         # build CSS + migrate + runserver  → http://localhost:8000
make css | css-watch | vendor     # Tailwind / unduh library JS
make fmt         # ruff check --fix + format
make check       # django check + lint + pytest (terakhir terverifikasi: 172 passed)
make wilayah-csv # bangun ulang apps/referensi/data/wilayah.csv (sumber: cahyadsn/wilayah, MIT, commit di-pin)
make prod-up | prod-down | prod-ps | prod-logs | prod-superuser | prod-seed | prod-backup   # butuh .env.prod
```

Pertama kali: `uv sync` → `cp .env.example .env` (isi `SECRET_KEY`) → `make up && make migrate && make seed && make superuser && make dev`.
Produksi lokal: salin `.env.prod.example` → `.env.prod` (secret acak, password DB sama di `DATABASE_URL`) → `make prod-up` → `http://localhost:8080`.
**Jangan** commit: `.env`, `.env.prod`, `bin/`, `static/css/app.css`, `backup-*.sql.gz`.

## 5. Struktur dan arsitektur

```
apps/
  core/        models.py (TimeStamped, SoftDelete)  registry.py (DatasetSpec)  dataset_views.py (CRUD generik)
               history.py  forms.py (StyledFormMixin)  mixins.py  context_processors.py (menu sidebar: NAV)
  accounts/    User (login email), Role, permissions (RoleRequiredMixin, SuperAdminRequiredMixin, has_role), CRUD pengguna
  imports/     readers.py (XLSX/CSV)  normalize.py (pilihan/wilayah)  engine.py (validasi + dry-run)
  referensi/   Provinsi, KabKota, AliasProvinsi, AliasKabKota, Periode, seed_wilayah, data/wilayah.csv
  sekolah/     Sekolah, dataset.py (spec), views/forms (dropdown kab/kota via HTMX), seed_demo_sekolah
config/  docker/  scripts/  static/ (css/input.css, vendor/)  templates/ (base, form, components/, dataset/, ...)  tests/
```

- **Modular monolith.** Satu app per area; logika bisnis (impor, agregasi chart) di modul terpisah dari view agar dapat dipakai ulang.
- **Dataset Registry** (`apps/core/registry.py`, `DatasetSpec`): `key, label, model, url_namespace, list_fields, form_fields, public_fields,
  search_fields, filter_fields, natural_key, time_field`. Mendorong tabel, formulir, kolom publik untuk Guest, pencarian, filter, target impor,
  dan chart. `public_fields` harus bagian dari `list_fields`. View generik di `dataset_views.py`; dataset baru cukup `spec` + subclass view.
  `spec.visible_fields(user)` menentukan kolom yang dikirim ke pengguna.
- **Menambah field:** ubah model → `make makemigrations && make migrate` → tambahkan ke `list_fields`/`form_fields` (dan `public_fields` bila
  publik) di spec. Tabel/formulir/filter ikut berubah.
- **Menambah dataset:** (1) model turunan `SoftDeleteModel` + `history = HistoricalRecords()`; (2) migrasi; (3) `DatasetSpec` dan daftarkan di
  `apps.py` (`ready`); (4) view + URL (subclass view generik); (5) menu di `NAV`; (6) tes matriks peran + tes Guest tidak menerima kolom terbatas;
  (7) integrasi ke wizard impor.
- **Soft delete:** `objects` = hanya yang aktif, `all_objects` = semuanya. **Pengecekan keunikan harus memakai `all_objects`.**
- **Riwayat:** pelaku dicatat `HistoryRequestMiddleware`. Penampil memakai pembanding sendiri (`core/history.py`) karena `diff_against`
  bawaan pustaka melewatkan field non-editable (mis. `deleted_at`). Menyimpan tanpa perubahan tidak boleh membuat catatan riwayat.
- **Rute:** `/`, `/healthz`, `/masuk/`, `/keluar/` (POST), `/pengguna/…`, `/referensi/periode/…`, `/referensi/wilayah/`, `/sekolah/…`
  (daftar, tambah, ubah, hapus, riwayat, terhapus, pulihkan, opsi-kabkota), `/admin/` (Django admin, hanya Super Admin).
- **Formulir:** `StyledFormMixin` + `templates/form.html` + `FormPageMixin`. Kelas Tailwind di file Python ikut dipindai → `make css` setelah mengubah kelas.

## 6. Peran dan hak akses

Nilai peran di DB: `viewer`, `admin`, `super_admin`. Guest tidak punya akun. Akun dibuat Super Admin (tanpa pendaftaran mandiri).
Belum login → redirect ke `/masuk/`; peran kurang → 403.

| Kemampuan | Guest | Viewer | Admin | Super Admin |
|---|---|---|---|---|
| Agregat, KPI, chart, peta; daftar sekolah dasar; status surat sudah/belum | ✔ | ✔ | ✔ | ✔ |
| Hasil baseline per sekolah, jumlah guru, rincian intervensi, tautan/berkas surat | – | ✔ | ✔ | ✔ |
| Tambah/edit/hapus (soft), impor, lihat riwayat | – | – | ✔ | ✔ |
| Rollback batch impor | – | – | milik sendiri | semua |
| Pengguna, referensi (periode, wilayah), audit, pulihkan/hapus permanen | – | – | – | ✔ |

Admin tidak dibatasi wilayah. Kolom publik Sekolah untuk Guest: NPSN, nama, provinsi, kab/kota, status, pengusul, mapel KKA (**bukan** jumlah guru).

## 7. Data dan keputusan domain

- **Sekolah:** `npsn` (teks 8 digit, unik termasuk terhadap data terhapus), `nama`, `jenjang` (hanya `SMP`), `provinsi`/`kabkota` (FK; kab/kota harus
  di provinsi yang sama), `status` (`negeri`/`swasta`), `pengusul` (`dinas`/`mitra`, tampil “Dinas Pendidikan”/“Mitra”; file sumber menulis “Pemda” = dinas),
  `mapel_kka` (`pelaksana`/`bukan`), `jumlah_guru` (opsional), `extra` (JSON untuk kolom yang belum punya kolom sendiri).
- **Wilayah:** 38 provinsi + 514 kab/kota, nama resmi Kepmendagri 300.2.2-2430/2025 (mis. “Daerah Khusus Ibukota Jakarta”,
  “Kota Administrasi Jakarta Pusat”). Variasi penulisan ditangani **alias** (dikelola lewat `/admin/`).
- **Periode:** master dikelola Super Admin (Baseline, Monitoring n, Endline); `tanggal_mulai` wajib (sumbu waktu chart).
- **Format impor:** hanya `.xlsx` dan `.csv` (`.xls`/`.xlsm` ditolak). CSV: encoding (utf-8/windows-1252) dan pemisah dipilih Admin.
- **Prinsip impor lengkap:** pemetaan manual; profil pemetaan dapat disimpan dan dipakai ulang hanya bila header identik (tetap ditinjau);
  selalu **dry-run + ringkasan** sebelum simpan; simpan dalam **satu transaksi**; batch tercatat dan **bisa di-rollback**; unggah ulang tidak
  menggandakan data. Kunci pencocokan: Sekolah = NPSN · Hasil Baseline = NPSN + periode · Surat = NPSN + jenis ·
  Intervensi = penyelenggara + pelaksana + judul + target mulai (atau kode kegiatan bila dipetakan). Token kosong bawaan: `#N/A`.
- **Bentuk file baseline asli:** header **dua baris** (grup bergabung sel + kode), data mulai baris 3, 71 kolom fisik (67 berisi data + 4 kosong): 10 profil, PM L3 (24), PM L2 (8),
  PM L1 (3), Skor PM, Profil PM, KKA L3 (10), KKA L2 (6), KKA L1 (2), Skor KKA, Profil KKA. Header digabung ` | `, mis. `PM Level 3 | 1.1.1`
  (kode `2.1` ada di PM dan KKA; grup yang membedakan). Rating: Pra-Berkembang, Berkembang, Maju, Unggul (null = Tidak Terkategori); ejaan “Pra Berkembang” /
  “Pra-Berkembang” / “Pra- Berkembang” sama artinya. Hasil indikator disimpan **format panjang** (sekolah, periode, kerangka, level, kode, rating).
- Codebook di workbook memuat 56 node hierarki dan 35 indikator Level 3; sheet data memberi rating untuk 34 indikator Level 3 (136 uraian rubrik). Pertahankan codebook lengkap; indikator tanpa kolom rating tidak mendapat hasil sampai sumbernya menjelaskan pemetaan.
- **Masalah data nyata yang harus tertangani (jangan diperbaiki diam-diam):** “Kab. Mimika” tertulis di provinsi “Papua” (kini Papua Tengah);
  “Kab. Klaten” tertulis di “D.I. Yogyakarta” (seharusnya Jawa Tengah); salah ketik “Kota Makasar”, “Kota Magelan”, “Kota Tarakan Barat”.
  Saran bagi Admin: petakan hanya kolom kab/kota dan biarkan provinsi diturunkan darinya.

## 8. Konvensi kode dan tes

- ruff, panjang baris 100. Pre-commit memakai `--force-exclude` (folder migrasi tidak diformat ulang).
- Tes: `pytest-django`; fixture di `tests/conftest.py` (`client_as(role)`, `make_user`, `wilayah`, `make_sekolah`). Tes “golden” memakai file asli di
  `tests/fixtures/` dan **dilewati bila file tidak ada**.
- Setiap fitur: tes matriks peran (Guest/Viewer/Admin/Super Admin), kasus error, dan—untuk data sensitif—tes bahwa respons Guest tidak memuatnya.
- Pesan commit: `feat:`, `fix:`, `chore:`. Teks antarmuka dan pesan error: Bahasa Indonesia, jelas dan dapat ditindaklanjuti.
- Keamanan: validasi upload (ukuran, tipe sebenarnya, nama acak, di luar jalur publik); escape sel ekspor yang diawali `= + - @`; jangan pernah
  menyajikan berkas unggahan lewat URL publik.

## 9. Jebakan yang sudah ditemui

- `AUTH_USER_MODEL` harus ditetapkan sebelum migrasi pertama. PostgreSQL di-pin ke 17.
- Hook pre-commit yang menerima path file eksplisit mengabaikan `extend-exclude` ruff → pakai `--force-exclude`.
- Jangan menyalin TAB ke Makefile (itulah alasan `.RECIPEPREFIX = >`).
- `diff_against` simple-history melewatkan field non-editable (lihat bagian 5).
- Dropdown kab/kota (HTMX) hanya mengisi ulang `<select>`; validasi server tetap membatasi pilihan menurut provinsi.
- Docker tidak dapat diuji di sandbox AI; konfigurasi produksi hanya terverifikasi oleh pemilik di WSL.
- `make seed-demo` membuat data fiktif (NPSN berawalan `99`, `extra.demo=true`) → hapus dengan `make demo-hapus` sebelum impor data asli.
- Mesin impor tahap 2.1 dijalankan lewat `import_dryrun`; konfigurasi kolom JSON ditulis dan ditinjau Admin secara manual. Untuk CSV, encoding serta delimiter wajib dipilih.

## 10. Status dan peta jalan

> Perbarui centang ini saat menyelesaikan langkah. Verifikasi dulu kondisi repo (`ls apps/`, `git log --oneline`, `make check`).

- [x] **Fase 0** — lingkungan, Django + PostgreSQL via Docker, health check, tes dasar
- [x] **1.1–1.2** — layout sidebar (Tailwind + HTMX + Alpine), akun email, 4 peran, login/logout
- [x] **1.3** — manajemen pengguna (Super Admin), data wilayah resmi, Periode
- [x] **1.4** — Dataset Registry, Sekolah (CRUD, riwayat, soft delete/pulihkan, dropdown HTMX), data demo
- [x] **Port tampilan prototipe** — shell, Beranda, dan Surat Dukungan dipindah ke template Django; KPI sekolah dinamis, fitur tanpa model ditampilkan sebagai belum tersedia
- [x] **1.5** — Docker produksi (Dockerfile bertahap, compose + Caddy, `make prod-*`), diverifikasi pemilik
- [x] **Fase 2 — Mesin impor** (inti produk)
  - [x] 2.1 pembaca xlsx/csv aman, header bertingkat + sel gabungan, normalisasi (pilihan, wilayah), validasi + dry-run, perintah `import_dryrun`, `default_aliases` pada spec
  - [x] 2.2 model `ImportBatch`, `MappingProfile`, `ValueAlias`; FK `import_batch` pada model yang diimpor; commit transaksional; rollback
  - [x] 2.3 wizard UI (HTMX): unggah → sheet/header → pemetaan kolom (aksi massal) → profil → pemetaan nilai → dry-run → mode/konflik → simpan
  - [x] 2.4 laporan error `.xlsx`, riwayat batch, unduh file asli, tombol rollback
- [x] **Fase 3 — Baseline** — `HasilBaseline`, `KamusIndikator`, `HasilIndikator` (format panjang); impor lebar→panjang; donut PM/KKA; Panduan Indikator;
  detail sekolah + edit indikator; **komponen chart perkembangan generik** (dataset ber-`time_field`)
  - [x] Model baseline dan relasi hierarki kamus indikator; skor tersimpan dengan presisi sumber
  - [x] Kamus indikator dan panduan rating PM/KKA diekstrak dari workbook sumber; perintah `seed_baseline_reference` aman dijalankan ulang
  - [x] Transformasi rating lebar→panjang dengan pemetaan kolom eksplisit; sel kosong tidak menimpa nilai
  - [x] Dry-run baseline memvalidasi pemetaan, NPSN, sekolah, periode, skor/profil, rating, dan pembaruan tanpa menulis DB
  - [x] Commit transaksional dengan riwayat, atribusi batch, serta rollback ringkasan dan indikator
  - [x] Wizard Admin unggah → pilih sheet/header → pemetaan manual → dry-run → alias rating → commit; batch muncul di riwayat impor
  - [x] Dashboard agregat dan donut PM/KKA; Guest tidak menerima data sekolah
  - [x] Panduan indikator publik; detail hasil untuk Viewer+; edit rating ber-riwayat untuk Admin+
  - [x] Komponen SVG perkembangan generik berdasarkan field waktu; detail sekolah menampilkan tren skor lintas periode
- [x] **Fase 4 — Beranda** — KPI, peta choropleth 38 provinsi (GeoJSON tanpa API key), tabel per provinsi, filter bersama, endpoint agregat publik; tes Guest
  - [x] Filter bersama untuk KPI dan tabel seluruh provinsi; endpoint agregat hanya mengirim hitungan publik
  - [x] Peta choropleth lokal tanpa CDN, dapat dipilih dengan mouse/keyboard; kode Papua hasil pemekaran dipetakan eksplisit dan dicocokkan ke kode Kemendagri
- [ ] **Fase 5 — Surat Dukungan** — tautan Drive + unggah PDF (≤10 MB, akses berizin), 4 donut kelengkapan, chart kumulatif
- [ ] **Fase 6 — Intervensi** — 3 penyelenggara; KPI status, kategori, unsur terlibat (M2M), jadwal bulanan, rencana vs realisasi, kumulatif
- [ ] **Fase 7 — Hardening dan deploy final** — rate limit login, header keamanan, audit dependensi, cadangan + uji restore, domain/HTTPS, README/runbook/panduan Admin, UAT
- [ ] **Fase 8 — Setelah rilis** — Kurasi & RTL (butuh spesifikasi), ekspor, edit massal, MFA, analitik/prediksi (peran DB read-only, pandas; baru bermakna setelah beberapa periode)
- [ ] **Backlog** — README, CI GitHub Actions (lint + tes + Postgres), halaman 404/500, halaman ubah kata sandi sendiri, aturan hapus Periode, aksesibilitas

## 11. Cara bekerja dengan pemilik

Pemilik berpengalaman dengan Ubuntu, git, dan Python, tetapi baru di Django; bekerja di WSL2 dan menyalin langsung dari jawaban AI.
Beri langkah kecil dengan: tujuan → perintah → **isi file lengkap** (bukan potongan) → cara memeriksa hasil → kriteria selesai.
Tanyakan bila terhalang; jangan mengarang kebutuhan.

## 12. Pertanyaan terbuka (butuh jawaban pemilik)

1. Provenance upstream GeoJSON perlu ditinjau kembali sebelum aset peta dipakai dalam distribusi produksi/komersial (lisensi dataset CC BY 4.0; lihat `static/data/README.md`).
2. Spesifikasi Kurasi dan Rencana Tindak Lanjut.
3. Pelaksana intervensi: teks bebas atau tabel master per penyelenggara? (saran: master)
4. Status intervensi: eksplisit atau diturunkan dari tanggal realisasi? (saran: eksplisit + validasi)
5. Apakah agregat publik perlu menyembunyikan kelompok yang sangat kecil?
6. Contoh file intervensi dan surat dukungan (kolom dan format).
7. Tanggal sebenarnya Periode Baseline.
8. Domain dan hosting akhir.
