/**
 * Mock dataset – mirrors what init_db.py generates but lives entirely in JS.
 * Covers a representative subset of land tiles at 10°×10° resolution.
 */

const MOCK_TILE_SIZE = 10;

function _classify(latC, lonC) {
  if (7 <= latC && latC <= 72 && -168 <= lonC && lonC <= -52) {
    if (58 <= latC && latC <= 65 && -95 <= lonC && lonC <= -78) return false;
    if (18 <= latC && latC <= 28 && -97 <= lonC && lonC <= -82) return false;
    return true;
  }
  if (58 <= latC && latC <= 84 && -73 <= lonC && lonC <= -12) return true; // Greenland
  if (-57 <= latC && latC <= 12 && -82 <= lonC && lonC <= -33) return true; // S. America
  if (35 <= latC && latC <= 72 && -12 <= lonC && lonC <= 32) return true;   // Europe
  if (50 <= latC && latC <= 70 && 32 <= lonC && lonC <= 62) return true;    // E. Europe / W. Russia
  if (-38 <= latC && latC <= 38 && -18 <= lonC && lonC <= 52) return true;  // Africa
  if (-27 <= latC && latC <= -12 && 43 <= lonC && lonC <= 51) return true;  // Madagascar
  if (12 <= latC && latC <= 38 && 32 <= lonC && lonC <= 62) return true;    // Middle East
  if (5 <= latC && latC <= 38 && 62 <= lonC && lonC <= 100) {
    if (5 <= latC && latC <= 18 && 83 <= lonC && lonC <= 98) return false; // Bay of Bengal
    return true;
  }
  if (48 <= latC && latC <= 75 && 55 <= lonC && lonC <= 180) return true;  // Russia/Siberia
  if (18 <= latC && latC <= 52 && 100 <= lonC && lonC <= 148) {
    if (35 <= latC && latC <= 45 && 130 <= lonC && lonC <= 140) return false; // Sea of Japan
    return true;
  }
  if (3 <= latC && latC <= 28 && 92 <= lonC && lonC <= 110) return true;   // SE Asia mainland
  if (-10 <= latC && latC <= 18 && 95 <= lonC && lonC <= 130) return true; // Maritime SE Asia
  if (-42 <= latC && latC <= -12 && 112 <= lonC && lonC <= 155) return true; // Australia
  if (-47 <= latC && latC <= -35 && 166 <= lonC && lonC <= 178) return true; // New Zealand
  if (63 <= latC && latC <= 67 && -25 <= lonC && lonC <= -13) return true; // Iceland
  if (latC <= -68) return true; // Antarctica
  return false;
}

function _buildTiles() {
  const tiles = [];
  let id = 1;
  for (let lat = -90; lat < 90; lat += MOCK_TILE_SIZE) {
    for (let lon = -180; lon < 180; lon += MOCK_TILE_SIZE) {
      const latMax = Math.min(lat + MOCK_TILE_SIZE, 90);
      const lonMax = Math.min(lon + MOCK_TILE_SIZE, 180);
      const cLat = (lat + latMax) / 2;
      const cLon = (lon + lonMax) / 2;
      if (_classify(cLat, cLon)) {
        tiles.push({
          id,
          lat_min: lat, lat_max: latMax,
          lon_min: lon, lon_max: lonMax,
          center_lat: Math.round(cLat * 10000) / 10000,
          center_lon: Math.round(cLon * 10000) / 10000,
          tile_size: MOCK_TILE_SIZE,
          is_land: true,
          status: "NOT_STARTED",
          coverage_count: 0,
          last_captured_at: null,
          notes: null,
        });
        id++;
      }
    }
  }
  return tiles;
}

// Build once, then mutate in-memory to simulate persistence within the session
const MOCK_TILES = _buildTiles();

// Pre-seed a few tiles with demo states
if (MOCK_TILES.length >= 3) {
  const now = new Date();
  MOCK_TILES[0].status = "COMPLETED";
  MOCK_TILES[0].coverage_count = 1;
  MOCK_TILES[0].last_captured_at = new Date(now - 28 * 86400e3).toISOString();

  MOCK_TILES[1].status = "IN_PROGRESS";
}

let _orderIdSeq = 1;
const MOCK_ORDERS = [];

if (MOCK_TILES.length >= 3) {
  const now = new Date();
  MOCK_ORDERS.push({
    id: _orderIdSeq++,
    tile_id: MOCK_TILES[0].id,
    center_lat: MOCK_TILES[0].center_lat,
    center_lon: MOCK_TILES[0].center_lon,
    target_name: `Demo – tile ${MOCK_TILES[0].id}`,
    scheduled_start: new Date(now - 30 * 86400e3).toISOString(),
    scheduled_end: new Date(now - 28 * 86400e3).toISOString(),
    resolution_m: 5, sensor_mode: "MULTISPECTRAL",
    max_cloud_pct: 15, sun_elev_min: 20, off_nadir_max: 25,
    priority: 8, status: "COMPLETED",
    created_at: new Date(now - 31 * 86400e3).toISOString(),
    updated_at: new Date(now - 28 * 86400e3).toISOString(),
    completed_at: new Date(now - 28 * 86400e3).toISOString(),
    notes: "First completed scene.",
  });
  MOCK_ORDERS.push({
    id: _orderIdSeq++,
    tile_id: MOCK_TILES[1].id,
    center_lat: MOCK_TILES[1].center_lat,
    center_lon: MOCK_TILES[1].center_lon,
    target_name: `Demo – tile ${MOCK_TILES[1].id}`,
    scheduled_start: new Date(now - 2 * 86400e3).toISOString(),
    scheduled_end: new Date(now + 1 * 86400e3).toISOString(),
    resolution_m: 1, sensor_mode: "PANCHROMATIC",
    max_cloud_pct: 10, sun_elev_min: 30, off_nadir_max: 20,
    priority: 7, status: "IN_PROGRESS",
    created_at: new Date(now - 3 * 86400e3).toISOString(),
    updated_at: new Date(now - 2 * 86400e3).toISOString(),
    completed_at: null,
    notes: "High-res panchromatic pass.",
  });
  MOCK_ORDERS.push({
    id: _orderIdSeq++,
    tile_id: MOCK_TILES[2].id,
    center_lat: MOCK_TILES[2].center_lat,
    center_lon: MOCK_TILES[2].center_lon,
    target_name: `Demo – tile ${MOCK_TILES[2].id}`,
    scheduled_start: new Date(now + 7 * 86400e3).toISOString(),
    scheduled_end: new Date(now + 10 * 86400e3).toISOString(),
    resolution_m: 10, sensor_mode: "SAR",
    max_cloud_pct: 100, sun_elev_min: null, off_nadir_max: 30,
    priority: 5, status: "PLANNED",
    created_at: now.toISOString(),
    updated_at: now.toISOString(),
    completed_at: null,
    notes: "SAR pass, cloud-independent.",
  });
}
