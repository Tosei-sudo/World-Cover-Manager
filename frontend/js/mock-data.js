/**
 * Mock dataset – mirrors what init_db.py generates but lives entirely in JS.
 * Land tile grid + sample satellites + simulated orbital passes.
 */

const MOCK_TILE_SIZE = 10;

// ── Land tile generation ───────────────────────────────────────────────────

function _classify(latC, lonC) {
  if (7 <= latC && latC <= 72 && -168 <= lonC && lonC <= -52) {
    if (58 <= latC && latC <= 65 && -95 <= lonC && lonC <= -78) return false;
    if (18 <= latC && latC <= 28 && -97 <= lonC && lonC <= -82) return false;
    return true;
  }
  if (58 <= latC && latC <= 84 && -73 <= lonC && lonC <= -12) return true;
  if (-57 <= latC && latC <= 12 && -82 <= lonC && lonC <= -33) return true;
  if (35 <= latC && latC <= 72 && -12 <= lonC && lonC <= 32) return true;
  if (50 <= latC && latC <= 70 && 32 <= lonC && lonC <= 62) return true;
  if (-38 <= latC && latC <= 38 && -18 <= lonC && lonC <= 52) return true;
  if (-27 <= latC && latC <= -12 && 43 <= lonC && lonC <= 51) return true;
  if (12 <= latC && latC <= 38 && 32 <= lonC && lonC <= 62) return true;
  if (5 <= latC && latC <= 38 && 62 <= lonC && lonC <= 100) {
    if (5 <= latC && latC <= 18 && 83 <= lonC && lonC <= 98) return false;
    return true;
  }
  if (48 <= latC && latC <= 75 && 55 <= lonC && lonC <= 180) return true;
  if (18 <= latC && latC <= 52 && 100 <= lonC && lonC <= 148) {
    if (35 <= latC && latC <= 45 && 130 <= lonC && lonC <= 140) return false;
    return true;
  }
  if (3 <= latC && latC <= 28 && 92 <= lonC && lonC <= 110) return true;
  if (-10 <= latC && latC <= 18 && 95 <= lonC && lonC <= 130) return true;
  if (-42 <= latC && latC <= -12 && 112 <= lonC && lonC <= 155) return true;
  if (-47 <= latC && latC <= -35 && 166 <= lonC && lonC <= 178) return true;
  if (63 <= latC && latC <= 67 && -25 <= lonC && lonC <= -13) return true;
  if (latC <= -68) return true;
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
          id, lat_min: lat, lat_max: latMax, lon_min: lon, lon_max: lonMax,
          center_lat: Math.round(cLat * 10000) / 10000,
          center_lon: Math.round(cLon * 10000) / 10000,
          tile_size: MOCK_TILE_SIZE, is_land: true,
          status: "NOT_STARTED", coverage_count: 0,
          last_captured_at: null, notes: null,
        });
        id++;
      }
    }
  }
  return tiles;
}

const MOCK_TILES = _buildTiles();

// Pre-seed a few tiles
if (MOCK_TILES.length >= 3) {
  const now = new Date();
  MOCK_TILES[0].status = "COMPLETED";
  MOCK_TILES[0].coverage_count = 1;
  MOCK_TILES[0].last_captured_at = new Date(now - 28 * 86400e3).toISOString();
  MOCK_TILES[1].status = "IN_PROGRESS";
}

// ── Sample satellites ──────────────────────────────────────────────────────

const MOCK_SATELLITES = [
  {
    id: 1, name: "GRUS-1A", norad_id: 43802,
    tle_line1: "1 43802U 18092F   25170.50000000  .00001500  00000-0  12345-3 0  9990",
    tle_line2: "2 43802  97.5200 126.3000 0001200  90.0000 270.0000 15.19876543214321",
    tle_epoch: "2025-06-19T12:00:00Z",
    tle_updated_at: new Date().toISOString(),
    swath_width_km: 70, sensor_modes: "MULTISPECTRAL,PANCHROMATIC", min_resolution_m: 2.5,
    is_active: true, created_at: new Date().toISOString(),
    notes: "Axelspace GRUS-1A – 70 km swath, 2.5 m MSS / 0.7 m PAN (example TLE).",
  },
  {
    id: 2, name: "GRUS-1B", norad_id: 47941,
    tle_line1: "1 47941U 21028K   25170.50000000  .00001480  00000-0  11800-3 0  9990",
    tle_line2: "2 47941  97.5210 130.1000 0001150  91.0000 120.0000 15.20012345678901",
    tle_epoch: "2025-06-19T12:00:00Z",
    tle_updated_at: new Date().toISOString(),
    swath_width_km: 70, sensor_modes: "MULTISPECTRAL,PANCHROMATIC", min_resolution_m: 2.5,
    is_active: true, created_at: new Date().toISOString(),
    notes: "Axelspace GRUS-1B – 70 km swath, 2.5 m MSS / 0.7 m PAN (example TLE).",
  },
  {
    id: 3, name: "GRUS-1C", norad_id: 47942,
    tle_line1: "1 47942U 21028L   25170.50000000  .00001460  00000-0  11600-3 0  9990",
    tle_line2: "2 47942  97.5190 128.5000 0001180  92.0000 240.0000 15.20023456789012",
    tle_epoch: "2025-06-19T12:00:00Z",
    tle_updated_at: new Date().toISOString(),
    swath_width_km: 70, sensor_modes: "MULTISPECTRAL,PANCHROMATIC", min_resolution_m: 2.5,
    is_active: true, created_at: new Date().toISOString(),
    notes: "Axelspace GRUS-1C – 70 km swath, 2.5 m MSS / 0.7 m PAN (example TLE).",
  },
];

// ── Simulated passes ───────────────────────────────────────────────────────

let _passIdSeq = 1;

function _generateMockPasses() {
  const passes = [];
  const now = Date.now();
  const period_ms = 100 * 60 * 1000; // ~100-min LEO orbit

  // Generate passes for first 30 uncovered tiles per satellite
  const uncovered = MOCK_TILES.filter(t => t.status === "NOT_STARTED").slice(0, 40);

  for (const sat of MOCK_SATELLITES) {
    // Distribute tiles across the next 7 days with orbital spacing
    uncovered.forEach((tile, i) => {
      // Stagger passes: first pass 1-23 hours from now, then repeat every ~5 days
      const offsetMs = (i % 15) * period_ms * 2 + Math.floor(Math.random() * period_ms);
      const passStart = new Date(now + offsetMs);
      const durS = 90 + Math.floor(Math.random() * 240);
      const passEnd = new Date(passStart.getTime() + durS * 1000);
      passes.push({
        id: _passIdSeq++,
        satellite_id: sat.id,
        tile_id: tile.id,
        pass_start: passStart.toISOString(),
        pass_end: passEnd.toISOString(),
        duration_s: durS,
        computed_at: new Date().toISOString(),
      });
    });
  }

  passes.sort((a, b) => new Date(a.pass_start) - new Date(b.pass_start));
  return passes;
}

const MOCK_PASSES = _generateMockPasses();

// ── Orders ─────────────────────────────────────────────────────────────────

let _orderIdSeq = 1;
const MOCK_ORDERS = [];

if (MOCK_TILES.length >= 3) {
  const now = new Date();
  MOCK_ORDERS.push(
    { id: _orderIdSeq++, tile_id: MOCK_TILES[0].id, satellite_id: 1,
      center_lat: MOCK_TILES[0].center_lat, center_lon: MOCK_TILES[0].center_lon,
      target_name: `Demo – tile ${MOCK_TILES[0].id}`,
      scheduled_start: new Date(now - 30 * 86400e3).toISOString(),
      scheduled_end:   new Date(now - 28 * 86400e3).toISOString(),
      resolution_m: 10, sensor_mode: "MULTISPECTRAL", max_cloud_pct: 15,
      sun_elev_min: 20, off_nadir_max: 25, priority: 8, status: "COMPLETED",
      created_at: new Date(now - 31 * 86400e3).toISOString(),
      updated_at: new Date(now - 28 * 86400e3).toISOString(),
      completed_at: new Date(now - 28 * 86400e3).toISOString(), notes: "First completed scene." },
    { id: _orderIdSeq++, tile_id: MOCK_TILES[1].id, satellite_id: 2,
      center_lat: MOCK_TILES[1].center_lat, center_lon: MOCK_TILES[1].center_lon,
      target_name: `Demo – tile ${MOCK_TILES[1].id}`,
      scheduled_start: new Date(now - 2 * 86400e3).toISOString(),
      scheduled_end:   new Date(now + 1 * 86400e3).toISOString(),
      resolution_m: 10, sensor_mode: "MULTISPECTRAL", max_cloud_pct: 10,
      sun_elev_min: 30, off_nadir_max: 20, priority: 7, status: "IN_PROGRESS",
      created_at: new Date(now - 3 * 86400e3).toISOString(),
      updated_at: new Date(now - 2 * 86400e3).toISOString(),
      completed_at: null, notes: "In-progress." },
    { id: _orderIdSeq++, tile_id: MOCK_TILES[2].id, satellite_id: 3,
      center_lat: MOCK_TILES[2].center_lat, center_lon: MOCK_TILES[2].center_lon,
      target_name: `Demo – tile ${MOCK_TILES[2].id}`,
      scheduled_start: new Date(now + 7 * 86400e3).toISOString(),
      scheduled_end:   new Date(now + 10 * 86400e3).toISOString(),
      resolution_m: 15, sensor_mode: "PANCHROMATIC", max_cloud_pct: 20,
      sun_elev_min: null, off_nadir_max: 30, priority: 5, status: "PLANNED",
      created_at: now.toISOString(), updated_at: now.toISOString(),
      completed_at: null, notes: "Planned via next-target suggestion." }
  );
}
