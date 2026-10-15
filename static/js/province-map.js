(() => {
  const map = document.querySelector(".province-map");
  if (!map) return;

  // Sumber geometri memberi kode lama 91/92 yang berulang untuk Papua.
  // Empat kode pemekaran ditetapkan eksplisit memakai nama fitur sumber.
  const papuaCodes = {
    "Papua Selatan": "93",
    "Papua Tengah": "94",
    "Papua Pegunungan": "95",
    "Papua Barat Daya": "96",
  };
  const codeFor = (feature) =>
    papuaCodes[feature.properties.PROVINSI] || feature.properties.KODE_PROV;

  const collectPositions = (coordinates, positions = []) => {
    if (typeof coordinates[0] === "number") positions.push(coordinates);
    else coordinates.forEach((item) => collectPositions(item, positions));
    return positions;
  };

  const projectFeatures = (features, width, height) => {
    const positions = features.flatMap((feature) =>
      collectPositions(feature.geometry.coordinates),
    );
    const bounds = positions.reduce(
      (result, [longitude, latitude]) => ({
        minX: Math.min(result.minX, longitude),
        maxX: Math.max(result.maxX, longitude),
        minY: Math.min(result.minY, latitude),
        maxY: Math.max(result.maxY, latitude),
      }),
      { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity },
    );
    const padding = 8;
    const scale = Math.min(
      (width - padding * 2) / (bounds.maxX - bounds.minX),
      (height - padding * 2) / (bounds.maxY - bounds.minY),
    );
    const drawnWidth = (bounds.maxX - bounds.minX) * scale;
    const drawnHeight = (bounds.maxY - bounds.minY) * scale;
    const offsetX = (width - drawnWidth) / 2;
    const offsetY = (height - drawnHeight) / 2;
    return (point) => [
      offsetX + (point[0] - bounds.minX) * scale,
      offsetY + (bounds.maxY - point[1]) * scale,
    ];
  };

  const ringPath = (ring, project) =>
    ring
      .map((point, index) => {
        const [x, y] = project(point);
        return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ") + " Z";

  const geometryPath = (geometry, project) => {
    const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
    return polygons.map((polygon) => polygon.map((ring) => ringPath(ring, project)).join(" ")).join(" ");
  };

  const colorFor = (value, max) => {
    if (!value) return "#e5edf1";
    const ratio = max ? value / max : 0;
    const lightness = 82 - ratio * 40;
    return `hsl(202 56% ${lightness}%)`;
  };

  const loadMap = async () => {
    const [geoResponse, aggregateResponse] = await Promise.all([
      fetch(map.dataset.geojsonUrl),
      fetch(`${map.dataset.aggregateUrl}${window.location.search}`),
    ]);
    if (!geoResponse.ok || !aggregateResponse.ok) throw new Error("Data peta tidak tersedia");
    const [geojson, aggregates] = await Promise.all([
      geoResponse.json(),
      aggregateResponse.json(),
    ]);
    const counts = new Map(aggregates.provinsi.map((item) => [item.kode, item.total]));
    const max = Math.max(0, ...counts.values());
    const width = 1000;
    const height = 390;
    const project = projectFeatures(geojson.features, width, height);
    map.setAttribute("viewBox", `0 0 ${width} ${height}`);
    map.setAttribute("preserveAspectRatio", "xMidYMid meet");

    geojson.features.forEach((feature) => {
      const code = codeFor(feature);
      const count = counts.get(code) || 0;
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", geometryPath(feature.geometry, project));
      path.setAttribute("fill", colorFor(count, max));
      path.setAttribute("class", "province-shape");
      path.setAttribute("tabindex", "0");
      path.setAttribute("role", "button");
      path.setAttribute("aria-label", `${feature.properties.PROVINSI}: ${count} sekolah. Pilih untuk memfilter.`);
      const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
      title.textContent = `${feature.properties.PROVINSI}: ${count} sekolah`;
      path.append(title);
      const selectProvince = () => {
        const params = new URLSearchParams(window.location.search);
        params.set("provinsi", code);
        window.location.search = params.toString();
      };
      path.addEventListener("click", selectProvince);
      path.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          selectProvince();
        }
      });
      map.append(path);
    });
  };

  loadMap().catch(() => {
    map.closest(".province-map-wrap").querySelector(".map-error").hidden = false;
  });
})();
