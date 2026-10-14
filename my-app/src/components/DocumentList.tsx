import { documents } from '../data/dashboard';

export default function DocumentList() {
  return (
    <div className="card">
      <div className="card-head"><h3>Kurasi Dokumen Terkini</h3><a href="#" className="link">Kelola Verifikasi</a></div>
      {documents.map((d) => (
        <div className="doc" key={d.name}>
          <div><strong>{d.name}</strong><small className="muted">{d.meta}</small></div>
          <span className={`status ${d.tone}`}>{d.status}</span>
        </div>
      ))}
    </div>
  );
}
