import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Beranda from './pages/Beranda';
import SuratDukungan from './pages/SuratDukungan';

const Soon = () => <div className="card"><h3>Halaman ini belum dibuat</h3></div>;

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Beranda />} />
          <Route path="/surat-dukungan" element={<SuratDukungan />} />
          <Route path="*" element={<Soon />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
