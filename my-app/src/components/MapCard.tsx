// Placeholder map. Swap the <svg> for react-leaflet / a GeoJSON choropleth later.
export default function MapCard() {
  return (
    <div className="card">
      <div className="card-head">
        <div><h3>Sebaran Sekolah SMP per Provinsi</h3><p className="muted">38 provinsi • arahkan kursor untuk melihat rincian</p></div>
        <span className="tag">Nasional</span>
      </div>
      <div className="map">
        <div className="zoom"><button>+</button><button>-</button></div>
        <svg viewBox="0 0 500 260" width="100%">
          <polygon points="60,40 80,40 150,150 125,165" fill="#5b9bf5" />
          <polygon points="200,60 255,50 265,90 225,105 205,90" fill="#93c5fd" />
          <polygon points="300,60 340,60 330,110 310,95" fill="#3b82f6" />
          <polygon points="380,60 450,70 440,130 400,120" fill="#93c5fd" />
          <polygon points="130,185 270,200 270,208 130,195" fill="#1e3a8a" />
        </svg>
        <div className="legend"><span>0 sekolah</span><i /><span>40+ sekolah</span></div>
      </div>
    </div>
  );
}
