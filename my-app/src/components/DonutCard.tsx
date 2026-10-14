interface Props { title: string; tone: 'blue' | 'green'; percent: number; sudah: number; belum: number; desc: string }

const R = 52;
const C = 2 * Math.PI * R;

export default function DonutCard({ title, tone, percent, sudah, belum, desc }: Props) {
  return (
    <div className="card donut-card">
      <p className={`donut-title ${tone}`}>{title}</p>
      <div className="donut-wrap">
        <svg viewBox="0 0 140 140">
          <circle cx="70" cy="70" r={R} fill="none" strokeWidth="12" stroke={belum > 0 ? '#f59e0b' : '#2563eb'} />
          <circle cx="70" cy="70" r={R} fill="none" strokeWidth="12" stroke="#2563eb"
            strokeDasharray={`${(C * percent) / 100} ${C}`} transform="rotate(-90 70 70)" />
        </svg>
        <div className="donut-center"><strong>{percent}%</strong><small>Sudah Ada</small></div>
      </div>
      <div className="donut-legend">
        <span><i className="dot blue" /> Sudah Ada<br />({sudah})</span>
        <span><i className="dot orange" /> Belum Ada<br />({belum})</span>
      </div>
      <p className="donut-desc">{desc}</p>
    </div>
  );
}
