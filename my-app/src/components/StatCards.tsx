import { Building2, Home, Users, Monitor } from 'lucide-react';
import { stats } from '../data/dashboard';

const icons = { building: <Building2 size={18} />, home: <Home size={18} />, users: <Users size={18} />, monitor: <Monitor size={18} /> };

export default function StatCards() {
  return (
    <section className="stats">
      {stats.map((s) => (
        <div className="card stat" key={s.label}>
          <div className="stat-top">
            <span className="stat-label">{s.label}</span>
            <span className="icon-box">{icons[s.icon]}</span>
          </div>
          <div className="stat-value">{s.value}</div>
          {'subs' in s ? (
            <div className="stat-subs">
              {s.subs.map((x) => (<span key={x.text}><span className={`dot ${x.tone}`} /> {x.text}</span>))}
            </div>
          ) : (<small className="muted">{s.note}</small>)}
        </div>
      ))}
    </section>
  );
}
