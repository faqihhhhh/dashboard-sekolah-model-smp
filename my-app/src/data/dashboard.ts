export type Tone = 'blue' | 'orange' | 'green';

export const navGroups = [
  { title: 'PROGRAM', items: ['Beranda', 'Surat Dukungan', 'Baseline Sekolah'] },
  { title: 'INTERVENSI', items: ['Direktorat SMP', 'BBPMP/BPMP', 'Dinas Pendidikan'] },
  { title: 'SEKOLAH', items: ['Kurasi', 'Rencana Tindak Lanjut'] },
];

export const stats = [
  { label: 'TOTAL SEKOLAH', value: 312, icon: 'building', subs: [{ tone: 'blue', text: '186 Negeri' }, { tone: 'orange', text: '126 Swasta' }] },
  { label: 'USULAN DINAS PENDIDIKAN', value: 198, icon: 'home', subs: [{ tone: 'blue', text: '180 Negeri' }, { tone: 'orange', text: '18 Swasta' }] },
  { label: 'USULAN MITRA', value: 114, icon: 'users', subs: [{ tone: 'blue', text: '6 Negeri' }, { tone: 'orange', text: '108 Swasta' }] },
  { label: 'MAPEL KKA / AI SMP', value: 105, icon: 'monitor', note: 'Sekolah dengan Kurikulum KKA Aktif' },
] as const;

export const provinces = [
  { name: 'Prov. Jawa Barat', total: 42 },
  { name: 'Prov. Jawa Timur', total: 36 },
  { name: 'Prov. Jawa Tengah', total: 28 },
  { name: 'Prov. Nusa Tenggara Timur', total: 17 },
  { name: 'Prov. Sumatera Utara', total: 19 },
  { name: 'Prov. Sulawesi Selatan', total: 14 },
  { name: 'Prov. D.I. Yogyakarta', total: 12 },
  { name: 'Prov. Lampung', total: 11 },
];

export const baseline = [
  { label: 'Laboratorium Komputer & Chromebook Terverifikasi', percent: 84, detail: '262 / 312 SMP', tone: 'blue' as Tone },
  { label: 'Guru Terlatih Modul Koding & Algoritma (Kemendikdasmen)', percent: 68, detail: '212 / 312 SMP', tone: 'orange' as Tone },
  { label: 'Surat Dukungan Dinas Pendidikan Kab/Kota Terbit', percent: 92, detail: '287 / 312 SMP', tone: 'green' as Tone },
];

export const documents = [
  { name: 'SMP Negeri 1 Surabaya', meta: 'Jawa Timur • Usulan Pemda', status: 'Lolos SK', tone: 'green' as Tone },
  { name: 'SMP Islam Al-Azhar 9 Bekasi', meta: 'Jawa Barat • Usulan Mitra', status: 'Review Lab', tone: 'orange' as Tone },
  { name: 'SMP Negeri 2 Kupang', meta: 'NTT • Usulan Pemda', status: 'Diterima', tone: 'blue' as Tone },
];
