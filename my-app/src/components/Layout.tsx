import { Outlet } from 'react-router-dom';
import Sidebar from '../files (3)/Sidebar';
import Topbar from '../files (3)/Topbar';
import Footer from './Footer';

export default function Layout() {
  return (
    <div className="layout">
      <Sidebar />
      <div className="main">
        <Topbar />
        <main className="content"><Outlet /></main>
        <Footer />
      </div>
    </div>
  );
}
