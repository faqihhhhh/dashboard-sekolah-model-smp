import { useMemo, useState } from 'react';
import { Search, RefreshCw, Eye } from 'lucide-react';
import { schools } from '../data/suratDukungan';

const PAGE_SIZE = 10;

function pageList(current: number, total: number): (number | '...')[] {
  const nums = [...new Set([1, 2, 3, current - 1, current, current + 1, total])]
    .filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
  const out: (number | '...')[] = [];
  nums.forEach((n, i) => { if (i && n - nums[i - 1] > 1) out.push('...'); out.push(n); });
  return out;
}

function DocButton({ url }: { url?: string }) {
  return url
    ? <a className="btn-view" href={url} target="_blank" rel="noreferrer"><Eye size={14} /> Lihat</a>
    : <span className="btn-missing">Belum Unggah</span>;
}

export default function SchoolTable() {
  const [query, setQuery] = useState('');
  const [provinsi, setProvinsi] = useState('');
  const [usulan, setUsulan] = useState('');
  const [page, setPage] = useState(1);

  const provinsiOptions = useMemo(() => [...new Set(schools.map((s) => s.provinsi))].sort(), []);

  const filtered = useMemo(() => schools.filter((s) =>
    (!query || s.nama.toLowerCase().includes(query.toLowerCase()) || s.npsn.includes(query)) &&
    (!provinsi || s.provinsi === provinsi) &&
    (!usulan || s.usulan === usulan)), [query, provinsi, usulan]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const start = (current - 1) * PAGE_SIZE;
  const rows = filtered.slice(start, start + PAGE_SIZE);

  const onFilter = (fn: () => void) => { fn(); setPage(1); };
  const reset = () => { setQuery(''); setProvinsi(''); setUsulan(''); setPage(1); };

  return (
    <div className="card sd-table-card">
      <h3>Daftar Sekolah — Kelengkapan Surat Dukungan</h3>
      <p className="muted">Klik tombol "Lihat" untuk membuka dokumen di Google Drive atau verifikasi kelengkapan.</p>

      <div className="filters">
        <label className="field"><Search size={15} />
          <input placeholder="Cari nama sekolah / NPSN..." value={query} onChange={(e) => onFilter(() => setQuery(e.target.value))} />
        </label>
        <select value={provinsi} onChange={(e) => onFilter(() => setProvinsi(e.target.value))}>
          <option value="">Semua Provinsi</option>
          {provinsiOptions.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select value={usulan} onChange={(e) => onFilter(() => setUsulan(e.target.value))}>
          <option value="">Semua Pengusul</option>
          <option value="Dinas">Dinas</option>
          <option value="Mitra">Mitra</option>
        </select>
        <button className="btn-outline" onClick={reset}><RefreshCw size={14} /> Reset</button>
      </div>

      <div className="table-scroll">
        <table className="sd-table">
          <thead>
            <tr>
              <th>NO</th><th>NPSN</th><th>NAMA SEKOLAH</th><th>PROVINSI</th><th>KABUPATEN/KOTA</th><th>USULAN</th>
              <th className="center">SURAT REKOMENDASI<br />& DUKUNGAN DINAS</th>
              <th className="center">SURAT KESIAPAN &<br />KOMITMEN SATUAN</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s, i) => (
              <tr key={s.npsn}>
                <td>{start + i + 1}</td>
                <td><a className="npsn" href="#">{s.npsn}</a></td>
                <td><strong>{s.nama}</strong></td>
                <td>{s.provinsi}</td>
                <td>{s.kabupaten}</td>
                <td><span className={`chip ${s.usulan === 'Dinas' ? 'blue' : 'green'}`}>{s.usulan}</span></td>
                <td className="center"><DocButton url={s.suratDinas} /></td>
                <td className="center"><DocButton url={s.suratSatuan} /></td>
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={8} className="empty">Tidak ada data yang cocok.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <span className="muted">
          {filtered.length ? `Menampilkan ${start + 1} sampai ${start + rows.length} dari ${filtered.length} sekolah` : 'Tidak ada data'}
        </span>
        <div className="pages">
          <button disabled={current === 1} onClick={() => setPage(current - 1)}>Sebelumnya</button>
          {pageList(current, totalPages).map((p, i) =>
            p === '...' ? <span key={`d${i}`} className="muted">...</span>
              : <button key={p} className={p === current ? 'on' : ''} onClick={() => setPage(p)}>{p}</button>)}
          <button disabled={current === totalPages} onClick={() => setPage(current + 1)}>Selanjutnya</button>
        </div>
      </div>
    </div>
  );
}
