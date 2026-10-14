import Hero from '../components/Hero';
import StatCards from '../components/StatCards';
import MapCard from '../components/MapCard';
import ProvinceList from '../components/ProvinceList';
import BaselineCard from '../components/BaselineCard';
import DocumentList from '../components/DocumentList';

export default function Beranda() {
  return (
    <>
      <Hero />
      <StatCards />
      <div className="grid-2">
        <div className="col"><MapCard /><BaselineCard /></div>
        <div className="col"><ProvinceList /><DocumentList /></div>
      </div>
    </>
  );
}
