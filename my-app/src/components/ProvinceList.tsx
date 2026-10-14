import { provinces } from '../data/dashboard';

export default function ProvinceList() {
  return (
    <div className="card">
      <div className="card-head">
        <div><h3>Sekolah per Provinsi</h3><p className="muted">38 provinsi • 312 sekolah total</p></div>
        <a href="#" className="link">Lihat Semua →</a>
      </div>
      <div className="table-head"><span>PROVINSI</span><span>SEKOLAH</span></div>
      {provinces.map((p) => (
        <div className="table-row" key={p.name}>
          <span>{p.name}</span><span className="badge">{p.total}</span>
        </div>
      ))}
    </div>
  );
}
