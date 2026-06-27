/**
 * Map view – renders tile coverage as a coloured rectangle grid on a Leaflet map.
 */

const STATUS_COLORS = {
  NOT_STARTED: { fill: "#e8e8e8", border: "#aaa" },
  IN_PROGRESS:  { fill: "#f0a500", border: "#c07800" },
  COMPLETED:    { fill: "#2ecc71", border: "#27ae60" },
};

let _map = null;
let _tileLayerGroup = null;
let _selectedTile = null;

function initMap() {
  if (_map) return;

  _map = L.map("map", { center: [20, 10], zoom: 2 });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap contributors",
    maxZoom: 18,
  }).addTo(_map);

  _tileLayerGroup = L.layerGroup().addTo(_map);
}

function renderMapTiles(tiles) {
  if (!_map) initMap();
  _tileLayerGroup.clearLayers();

  for (const tile of tiles) {
    const col = STATUS_COLORS[tile.status] || STATUS_COLORS.NOT_STARTED;
    const rect = L.rectangle(
      [[tile.lat_min, tile.lon_min], [tile.lat_max, tile.lon_max]],
      {
        color: col.border,
        weight: 0.8,
        fillColor: col.fill,
        fillOpacity: 0.55,
      }
    );

    rect.bindTooltip(_tileTooltip(tile), { sticky: true });
    rect.on("click", () => onTileClick(tile));
    rect.addTo(_tileLayerGroup);
  }
}

function _tileTooltip(tile) {
  return `
    <b>Tile #${tile.id}</b><br>
    ${tile.lat_min}°–${tile.lat_max}° N,
    ${tile.lon_min}°–${tile.lon_max}° E<br>
    Status: <b>${tile.status.replace("_", " ")}</b><br>
    Covered: ${tile.coverage_count}×
  `;
}

function highlightTileOnMap(tileId) {
  _tileLayerGroup.eachLayer((layer) => {
    if (layer._tileId === tileId) {
      layer.setStyle({ weight: 3, color: "#0056b3" });
      _map.panTo(layer.getBounds().getCenter());
    }
  });
}
