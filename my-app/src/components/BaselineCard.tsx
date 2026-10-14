import { baseline } from '../data/dashboard';

export default function BaselineCard() {
  return (
    <div className="card">
      <div className="card-head">
        <div><h3>Baseline Kesiapan Sekolah Model SMP</h3><p className="muted">Pemenuhan standar prasyarat digital & pengajar</p></div>
        <span className="tag green-tag">Target Terpenuhi 81%</span>
      </div>
      {baseline.map((b) => (
        <div className="progress-item" key={b.label}>
          <div className="progress-label"><span>{b.label}</span><strong className={b.tone}>{b.percent}% ({b.detail})</strong></div>
          <div className="track"><div className={`bar ${b.tone}`} style={{ width: `${b.percent}%` }} /></div>
        </div>
      ))}
    </div>
  );
}
