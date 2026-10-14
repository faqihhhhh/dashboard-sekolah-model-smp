import { useState } from 'react';
import { Home, FileText, TrendingUp, Building2, Landmark, Users, ClipboardList, CheckCircle2 } from 'lucide-react';
import { navGroups } from '../data/dashboard';

const icons: Record<string, JSX.Element> = {
  'Beranda': <Home size={16} />, 'Surat Dukungan': <FileText size={16} />, 'Baseline Sekolah': <TrendingUp size={16} />,
  'Direktorat SMP': <Building2 size={16} />, 'BBPMP/BPMP': <Landmark size={16} />, 'Dinas Pendidikan': <Users size={16} />,
  'Kurasi': <ClipboardList size={16} />, 'Rencana Tindak Lanjut': <CheckCircle2 size={16} />,
};

export default function Sidebar() {
  const [active, setActive] = useState('Beranda');
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-name">Kemen<b>dikdasmen</b></div>
        <small>Direktorat Sekolah Menengah Pertama</small>
      </div>
      <nav>
        {navGroups.map((g) => (
          <div key={g.title}>
            <p className="nav-title">{g.title}</p>
            {g.items.map((item) => (
              <button key={item} className={`nav-item ${active === item ? 'active' : ''}`} onClick={() => setActive(item)}>
                {icons[item]} {item}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="sidebar-foot"><span className="dot green" /> Tahun Ajaran 2025/2026 <em>v2.4</em></div>
    </aside>
  );
}
