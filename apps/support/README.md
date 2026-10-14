# Surat Dukungan

Setiap sekolah dapat memiliki dua dokumen aktif: **Surat Rekomendasi dan Dukungan** serta
**Surat Kesiapan dan Komitmen Satuan**. Admin memilih satu sumber per dokumen: tautan Google Drive
(HTTPS) atau PDF yang diunggah (maksimal 10 MB). Berkas disimpan di `MEDIA_ROOT`, yang tidak
disajikan sebagai URL publik.

Guest melihat identitas sekolah dan status tersedia/belum tersedia. Viewer ke atas dapat membuka
dokumen melalui endpoint berizin; Admin ke atas dapat menambah, mengganti, atau menandai dokumen
belum tersedia. Penghapusan bersifat soft delete dan Super Admin dapat memulihkan dokumen.

Empat ringkasan menghitung kelengkapan menurut pengusul dan jenis surat. Grafik kumulatif memakai
waktu pencatatan dokumen di aplikasi (`created_at`), bukan tanggal yang tercetak pada surat.
