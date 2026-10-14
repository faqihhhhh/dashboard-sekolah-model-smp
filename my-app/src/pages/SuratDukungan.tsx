import { FileText, Download } from 'lucide-react';
import DonutCard from '../components/DonutCard';
import SchoolTable from '../components/SchoolTable';
import { summaries } from '../data/suratDukungan';
import './SuratDukungan.css';

export default function SuratDukungan() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="sm">Surat Dukungan</h1>
          <p className="muted">Rekap Surat Kesiapan Satuan Pendidikan dan Dukungan Dinas Pendidikan — Direktorat SMP</p>
        </div>
        <div className="head-actions">
          <button className="btn-outline"><FileText size={14} /> Panduan Format Surat</button>
          <button className="btn-green"><Download size={14} /> Unduh Rekapitulasi (.XLSX)</button>
        </div>
      </div>

      <section className="sd-cards">
        {summaries.map((s, i) => <DonutCard key={i} {...s} />)}
      </section>

      <SchoolTable />
    </>
  );
}
