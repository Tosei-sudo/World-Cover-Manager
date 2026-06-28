/**
 * Map view – coloured tile grid + satellite ground track overlay.
 */

const STATUS_COLORS = {
  NOT_STARTED: { fill: "#e8e8e8", border: "#aaa" },
  IN_PROGRESS:  { fill: "#f0a500", border: "#c07800" },
  COMPLETED:    { fill: "#2ecc71", border: "#27ae60" },
};

// One colour per satellite (cycled)
const TRACK_COLORS = ["#e74c3c", "#3498db", "#9b59b6", "#1abc9c", "#f39c12"];

let _map = null;
let _tileLayerGroup  = null;
let _trackLayerGroup = null;
let _sceneLayerGroup = null;

function initMap() {
  if (_map) return;
  _map = L.map("map", { center: [20, 10], zoom: 2 });

  if (CONFIG.TILE_SERVER_URL) {
    L.tileLayer(CONFIG.TILE_SERVER_URL, {
      attribution: CONFIG.TILE_ATTRIBUTION || "",
      maxZoom: 18,
    }).addTo(_map);
  }

  _tileLayerGroup  = L.layerGroup().addTo(_map);
  _sceneLayerGroup = L.layerGroup().addTo(_map);
  _trackLayerGroup = L.layerGroup().addTo(_map);
}

// ── Coverage tiles ─────────────────────────────────────────────────────────

function renderMapTiles(tiles) {
  if (!_map) initMap();
  _tileLayerGroup.clearLayers();

  for (const tile of tiles) {
    const col = STATUS_COLORS[tile.status] || STATUS_COLORS.NOT_STARTED;
    const rect = L.rectangle(
      [[tile.lat_min, tile.lon_min], [tile.lat_max, tile.lon_max]],
      { color: col.border, weight: 0.8, fillColor: col.fill, fillOpacity: 0.55 }
    );
    rect.bindTooltip(_tileTooltip(tile), { sticky: true });
    rect.on("click", () => onTileClick(tile));
    rect.addTo(_tileLayerGroup);
  }
}

function _tileTooltip(tile) {
  let tip = `<b>Tile #${tile.id}</b><br>
    ${tile.lat_min}°–${tile.lat_max}° N, ${tile.lon_min}°–${tile.lon_max}° E<br>
    Status: <b>${tile.status.replace("_", " ")}</b> · Covered: ${tile.coverage_count}×`;
  if (tile.coverage_pct > 0)
    tip += `<br>Footprint coverage: <b>${tile.coverage_pct.toFixed(1)}%</b>`;
  return tip;
}

// ── Scene footprints ───────────────────────────────────────────────────────

/**
 * Draw ingested scene footprints as semi-transparent amber polygons.
 * Replaces any previously drawn scene layer.
 */
function drawSceneFootprints(scenes) {
  if (!_map) return;
  _sceneLayerGroup.clearLayers();
  if (!scenes || scenes.length === 0) return;

  for (const scene of scenes) {
    try {
      const geom = JSON.parse(scene.footprint_geojson);
      const ring = geom.type === "Feature" ? geom.geometry.coordinates[0] : geom.coordinates[0];
      // GeoJSON is [lon, lat]; Leaflet wants [lat, lon]
      const latLons = ring.slice(0, -1).map(c => [c[1], c[0]]);
      const capturedDate = scene.captured_at
        ? new Date(scene.captured_at).toLocaleDateString()
        : "—";
      const cloudInfo = scene.cloud_cover_pct != null
        ? `<br>Cloud: ${scene.cloud_cover_pct}%`
        : "";
      L.polygon(latLons, {
        color: "#f59e0b",
        fillColor: "#fbbf24",
        fillOpacity: 0.28,
        weight: 2,
      })
        .bindPopup(`<b>Scene #${scene.id}</b><br>Captured: ${capturedDate}${cloudInfo}`)
        .addTo(_sceneLayerGroup);
    } catch { /* skip malformed */ }
  }
}

function clearSceneFootprints() {
  if (_sceneLayerGroup) _sceneLayerGroup.clearLayers();
}

// ── Ground track ───────────────────────────────────────────────────────────

/**
 * Draw (or replace) the ground track for one satellite.
 * @param {number} satId     - satellite id (used for colour selection)
 * @param {string} satName   - label shown on the polyline
 * @param {Array}  points    - [{lat, lon, time}, …]
 * @param {number} swathKm   - swath width; draws semi-transparent corridor
 */
function drawGroundTrack(satId, satName, points, swathKm) {
  if (!_map) return;

  // Remove existing track layers for this satellite
  _trackLayerGroup.eachLayer(l => {
    if (l._satId === satId) _trackLayerGroup.removeLayer(l);
  });

  if (!points || points.length === 0) return;

  const color = TRACK_COLORS[(satId - 1) % TRACK_COLORS.length];
  const latLons = points.map(p => [p.lat, p.lon]);

  // Main track line
  const trackLine = L.polyline(latLons, {
    color, weight: 2, opacity: 0.85, dashArray: "6 3",
  });
  trackLine._satId = satId;
  trackLine.bindTooltip(`${satName} ground track`, { sticky: false, direction: "top" });
  trackLine.addTo(_trackLayerGroup);

  // Swath corridor (buffered in degrees – approximate at low latitudes)
  const halfSwathDeg = swathKm / 2 / 111;
  const leftEdge  = points.map(p => [p.lat - halfSwathDeg, p.lon]);
  const rightEdge = [...points].reverse().map(p => [p.lat + halfSwathDeg, p.lon]);
  const swathPoly = L.polygon([...leftEdge, ...rightEdge], {
    color, weight: 0, fillColor: color, fillOpacity: 0.12,
  });
  swathPoly._satId = satId;
  swathPoly.addTo(_trackLayerGroup);

  // Start marker
  const startPt = points[0];
  const marker = L.circleMarker([startPt.lat, startPt.lon], {
    radius: 5, color, fillColor: color, fillOpacity: 0.9, weight: 1,
  });
  marker._satId = satId;
  marker.bindTooltip(`${satName}<br>${new Date(startPt.time).toUTCString()}`, { direction: "top" });
  marker.addTo(_trackLayerGroup);
}

function clearGroundTracks() {
  if (_trackLayerGroup) _trackLayerGroup.clearLayers();
}
