import { BookOpen, FileText, Download } from 'lucide-react';

export default function Hero() {
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Daftar Sekolah Model 2026 Sekolah Menengah Pertama</h1>
          <p className="muted">Implementasi Pembelajaran Mendalam & Koding dan Kecerdasan Artifisial (SMP)</p>
        </div>
        <button className="btn-outline"><Download size={14} /> Unduh Rekapitulasi (.XLSX)</button>
      </div>
      <section className="hero">
        <span className="pill"><span className="dot orange" /> Program Prioritas Nasional 2026</span>
        <h2>Sekolah Model Implementasi Pembelajaran Mendalam & Koding dan Kecerdasan Artifisial</h2>
        <p>
          Satuan pendidikan SMP yang dipilih sebagai sentra representasi implementasi Pembelajaran Mendalam,
          Penguatan Computational Thinking, serta Koding & Kecerdasan Artifisial. Berfungsi sebagai percontohan
          dan laboratorium inovasi pembelajaran tingkat menengah pertama.
        </p>
        <div className="hero-actions">
          <button className="btn-yellow"><BookOpen size={16} /> Panduan Penyelenggaraan</button>
          <button className="btn-ghost"><FileText size={16} /> SK Penetapan Sekolah Model</button>
        </div>
      </section>
    </>
  );
}
