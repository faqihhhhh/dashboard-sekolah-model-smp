import { useLocation } from 'react-router-dom';
import { Search, Bell, LogIn } from 'lucide-react';

export default function Topbar() {
  const { pathname } = useLocation();
  const placeholder = pathname === '/surat-dukungan'
    ? 'Cari dokumen surat, NPSN, nama sekolah...'
    : 'Cari sekolah SMP, SK penetapan, provinsi...';
  return (
    <header className="topbar">
      <div className="search">
        <Search size={16} />
        <input placeholder={placeholder} />
      </div>
      <div className="topbar-right">
        <span className="bell"><Bell size={18} /></span>
        <div className="avatar">DS</div>
        <div className="user"><strong>Direktorat SMP</strong><small>Admin Pusat</small></div>
        <button className="btn-primary"><LogIn size={16} /> Masuk</button>
      </div>
    </header>
  );
}
