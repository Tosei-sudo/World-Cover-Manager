/**
 * Map view – coloured tile grid + satellite ground track overlay.
 *
 * Coverage tiles are rendered via a custom L.GridLayer (canvas-based) instead
 * of individual L.rectangle elements.  This avoids creating thousands of SVG
 * DOM nodes and keeps the map responsive even with 10 000+ land tiles.
 */

const STATUS_COLORS = {
  NOT_STARTED: { fill: "#e8e8e8", border: "#aaa" },
  IN_PROGRESS:  { fill: "#f0a500", border: "#c07800" },
  COMPLETED:    { fill: "#2ecc71", border: "#27ae60" },
};

// One colour per satellite (cycled)
const TRACK_COLORS = ["#e74c3c", "#3498db", "#9b59b6", "#1abc9c", "#f39c12"];

let _map            = null;
let _coverageLayer  = null;
let _trackLayerGroup = null;
let _sceneLayerGroup = null;
let _mapTooltipEl   = null;


// ── Canvas-based coverage grid layer ────────────────────────────────────────

const CoverageLayer = L.GridLayer.extend({
  initialize(tiles, options) {
    L.GridLayer.prototype.initialize.call(this, options);
    this._data = [];
    this._tileMap = new Map();  // "lat_lon" → tile object for O(1) click lookup
    if (tiles && tiles.length) this._setData(tiles);
  },

  setTiles(tiles) {
    this._setData(tiles);
    this.redraw();
  },

  _setData(tiles) {
    this._data = tiles;
    this._tileMap.clear();
    for (const t of tiles) {
      // Key: rounded lat_min and lon_min avoids float precision issues
      const k = `${Math.round(t.lat_min * 1000)}_${Math.round(t.lon_min * 1000)}`;
      this._tileMap.set(k, t);
    }
    // Store tile size for bucket calculation (assume uniform grid)
    this._tileSize = tiles.length ? tiles[0].tile_size : 10;
  },

  createTile(coords) {
    const size = this.getTileSize();
    const canvas = document.createElement("canvas");
    canvas.width  = size.x;
    canvas.height = size.y;
    if (this._map) this._drawCanvas(canvas, coords, size);
    return canvas;
  },

  _drawCanvas(canvas, coords, size) {
    const ctx  = canvas.getContext("2d");
    const z    = coords.z;
    const ox   = coords.x * size.x;   // canvas origin in global Mercator pixels
    const oy   = coords.y * size.y;

    // Lat/lon bounds of this canvas tile (for spatial pre-filter)
    const nw  = this._map.unproject([ox,          oy         ], z);
    const se  = this._map.unproject([ox + size.x,  oy + size.y], z);
    const latMin = se.lat, latMax = nw.lat;
    const lonMin = nw.lng, lonMax = se.lng;

    const FILL_COLOR = { NOT_STARTED: "#e8e8e8", IN_PROGRESS: "#f0a500", COMPLETED: "#2ecc71" };

    for (const t of this._data) {
      // Spatial pre-filter (lat/lon overlap)
      if (t.lon_max <= lonMin || t.lon_min >= lonMax ||
          t.lat_max <= latMin || t.lat_min >= latMax) continue;

      // Project tile corners to global Mercator pixels, then into canvas coords
      const sw = this._map.project(L.latLng(t.lat_min, t.lon_min), z);
      const ne = this._map.project(L.latLng(t.lat_max, t.lon_max), z);

      const x1 = Math.round(sw.x - ox);
      const x2 = Math.round(ne.x - ox);
      const y1 = Math.round(ne.y - oy);   // note: y increases downward
      const y2 = Math.round(sw.y - oy);
      const w  = x2 - x1;
      const h  = y2 - y1;
      if (w <= 0 || h <= 0) continue;

      ctx.globalAlpha = 0.6;
      ctx.fillStyle   = FILL_COLOR[t.status] || "#e8e8e8";
      ctx.fillRect(x1, y1, w, h);
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = "rgba(0,0,0,0.12)";
      ctx.lineWidth   = 0.5;
      ctx.strokeRect(x1, y1, w, h);
    }
  },

  /** O(1) tile lookup by lat/lon (for click and hover). */
  getTileAt(lat, lon) {
    const sz  = this._tileSize || 10;
    const lk  = Math.floor(lat / sz) * sz;
    const lnk = Math.floor(lon / sz) * sz;
    const k   = `${Math.round(lk * 1000)}_${Math.round(lnk * 1000)}`;
    return this._tileMap.get(k) || null;
  },
});


// ── Map initialisation ────────────────────────────────────────────────────

function initMap() {
  if (_map) return;
  _map = L.map("map", { center: [20, 10], zoom: 2 });

  if (CONFIG.TILE_SERVER_URL) {
    L.tileLayer(CONFIG.TILE_SERVER_URL, {
      attribution: CONFIG.TILE_ATTRIBUTION || "",
      maxZoom: 18,
    }).addTo(_map);
  }

  _coverageLayer  = new CoverageLayer([], { pane: "overlayPane", zIndex: 200 }).addTo(_map);
  _sceneLayerGroup = L.layerGroup().addTo(_map);
  _trackLayerGroup = L.layerGroup().addTo(_map);

  // Floating tooltip
  _mapTooltipEl = document.createElement("div");
  _mapTooltipEl.id = "map-tile-tooltip";
  document.body.appendChild(_mapTooltipEl);

  // Hover → show tooltip
  _map.on("mousemove", e => {
    const t = _coverageLayer.getTileAt(e.latlng.lat, e.latlng.lng);
    if (t) {
      let html = `<b>Tile #${t.id}</b> · <b>${t.status.replace("_", " ")}</b>` +
        `<br>${t.lat_min}°–${t.lat_max}° N, ${t.lon_min}°–${t.lon_max}° E` +
        `<br>Covered: ${t.coverage_count}×`;
      if (t.coverage_pct > 0) html += ` · ${t.coverage_pct.toFixed(1)}%`;
      _mapTooltipEl.innerHTML = html;
      _mapTooltipEl.style.display  = "block";
      _mapTooltipEl.style.left = (e.originalEvent.clientX + 14) + "px";
      _mapTooltipEl.style.top  = (e.originalEvent.clientY - 36) + "px";
    } else {
      _mapTooltipEl.style.display = "none";
    }
  });
  _map.on("mouseout", () => { _mapTooltipEl.style.display = "none"; });

  // Click → open tile detail panel
  _map.on("click", e => {
    const t = _coverageLayer.getTileAt(e.latlng.lat, e.latlng.lng);
    if (t) onTileClick(t);
  });
}


// ── Coverage tiles (public API) ───────────────────────────────────────────

function renderMapTiles(tiles) {
  if (!_map) initMap();
  _coverageLayer.setTiles(tiles);
}


// ── Scene footprints ──────────────────────────────────────────────────────

function drawSceneFootprints(scenes) {
  if (!_map) return;
  _sceneLayerGroup.clearLayers();
  if (!scenes || scenes.length === 0) return;

  for (const scene of scenes) {
    try {
      const geom = JSON.parse(scene.footprint_geojson);
      const ring = geom.type === "Feature" ? geom.geometry.coordinates[0] : geom.coordinates[0];
      const latLons = ring.slice(0, -1).map(c => [c[1], c[0]]);
      const capturedDate = scene.captured_at
        ? new Date(scene.captured_at).toLocaleDateString() : "—";
      const cloudInfo = scene.cloud_cover_pct != null
        ? `<br>Cloud: ${scene.cloud_cover_pct}%` : "";
      L.polygon(latLons, {
        color: "#f59e0b", fillColor: "#fbbf24", fillOpacity: 0.28, weight: 2,
      })
        .bindPopup(`<b>Scene #${scene.id}</b><br>Captured: ${capturedDate}${cloudInfo}`)
        .addTo(_sceneLayerGroup);
    } catch { /* skip malformed */ }
  }
}

function clearSceneFootprints() {
  if (_sceneLayerGroup) _sceneLayerGroup.clearLayers();
}


// ── Ground track ──────────────────────────────────────────────────────────

function drawGroundTrack(satId, satName, points, swathKm) {
  if (!_map) return;

  _trackLayerGroup.eachLayer(l => {
    if (l._satId === satId) _trackLayerGroup.removeLayer(l);
  });

  if (!points || points.length === 0) return;

  const color  = TRACK_COLORS[(satId - 1) % TRACK_COLORS.length];
  const latLons = points.map(p => [p.lat, p.lon]);

  const trackLine = L.polyline(latLons, {
    color, weight: 2, opacity: 0.85, dashArray: "6 3",
  });
  trackLine._satId = satId;
  trackLine.bindTooltip(`${satName} ground track`, { sticky: false, direction: "top" });
  trackLine.addTo(_trackLayerGroup);

  // Swath corridor offset in the cross-track (longitude) direction
  const halfSwathDeg = swathKm / 2 / 111;
  const leftEdge = points.map(p => {
    const halfLon = halfSwathDeg / Math.max(0.01, Math.cos(p.lat * Math.PI / 180));
    return [p.lat, p.lon - halfLon];
  });
  const rightEdge = [...points].reverse().map(p => {
    const halfLon = halfSwathDeg / Math.max(0.01, Math.cos(p.lat * Math.PI / 180));
    return [p.lat, p.lon + halfLon];
  });
  const swathPoly = L.polygon([...leftEdge, ...rightEdge], {
    color, weight: 0, fillColor: color, fillOpacity: 0.12,
  });
  swathPoly._satId = satId;
  swathPoly.addTo(_trackLayerGroup);

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
