import { Search, Bell, LogIn } from 'lucide-react';

export default function Topbar() {
  return (
    <header className="topbar">
      <div className="search">
        <Search size={16} />
        <input placeholder="Cari sekolah SMP, SK penetapan, provinsi..." />
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
