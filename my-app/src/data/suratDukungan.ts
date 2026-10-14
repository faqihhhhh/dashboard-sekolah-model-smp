const DRIVE = 'https://drive.google.com/'; // ganti dengan link dokumen asli dari API

export interface School {
  npsn: string;
  nama: string;
  provinsi: string;
  kabupaten: string;
  usulan: 'Dinas' | 'Mitra';
  suratDinas?: string;   // kosong = "Belum Unggah"
  suratSatuan?: string;
}

export const summaries = [
  { title: 'USULAN DINAS PENDIDIKAN', tone: 'blue', percent: 100, sudah: 198, belum: 0, desc: 'Surat Rekomendasi dan Dukungan Dinas Pendidikan' },
  { title: 'USULAN DINAS PENDIDIKAN', tone: 'blue', percent: 98.5, sudah: 195, belum: 3, desc: 'Surat Kesiapan dan Komitmen Satuan Pendidikan' },
  { title: 'USULAN MITRA', tone: 'green', percent: 100, sudah: 114, belum: 0, desc: 'Surat Rekomendasi dan Dukungan Mitra Pembangunan' },
  { title: 'USULAN MITRA', tone: 'green', percent: 96.5, sudah: 110, belum: 4, desc: 'Surat Kesiapan dan Komitmen Satuan Pendidikan' },
] as const;

// Data contoh. Saat terhubung ke API (312 sekolah), tabel & paginasi otomatis menyesuaikan.
export const schools: School[] = [
  { npsn: '10107097', nama: 'SMP NEGERI 2 BIREUEN', provinsi: 'Prov. Aceh', kabupaten: 'Kab. Bireuen', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '10105399', nama: 'SMP NEGERI 2 BANDA ACEH', provinsi: 'Prov. Aceh', kabupaten: 'Kota Banda Aceh', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '10105388', nama: 'SMP NEGERI 3 BANDA ACEH', provinsi: 'Prov. Aceh', kabupaten: 'Kota Banda Aceh', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '50103126', nama: 'SMP NEGERI 2 DENPASAR', provinsi: 'Prov. Bali', kabupaten: 'Kota Denpasar', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '50103124', nama: 'SMP NEGERI 4 DENPASAR', provinsi: 'Prov. Bali', kabupaten: 'Kota Denpasar', usulan: 'Dinas', suratDinas: DRIVE },
  { npsn: '50103181', nama: 'SMPK SANTO YOSEPH DENPASAR', provinsi: 'Prov. Bali', kabupaten: 'Kota Denpasar', usulan: 'Mitra', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '20600451', nama: 'SMP NEGERI 1 PANDEGLANG', provinsi: 'Prov. Banten', kabupaten: 'Kab. Pandeglang', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '20532210', nama: 'SMP NEGERI 1 SURABAYA', provinsi: 'Prov. Jawa Timur', kabupaten: 'Kota Surabaya', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
  { npsn: '20223011', nama: 'SMPS ISLAM AL-AZHAR 9 BEKASI', provinsi: 'Prov. Jawa Barat', kabupaten: 'Kota Bekasi', usulan: 'Mitra', suratDinas: DRIVE },
  { npsn: '50305012', nama: 'SMP NEGERI 2 KUPANG', provinsi: 'Prov. Nusa Tenggara Timur', kabupaten: 'Kota Kupang', usulan: 'Dinas', suratDinas: DRIVE, suratSatuan: DRIVE },
];
