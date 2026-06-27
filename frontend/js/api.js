/**
 * API module – exposes the same interface whether using the real backend or
 * the in-memory mock.  Switch via CONFIG.MOCK_MODE in config.js.
 */

// ── Real API ─────────────────────────────────────────────────────────────────

async function _fetch(path, options = {}) {
  const res = await fetch(CONFIG.API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

const RealAPI = {
  tiles: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/tiles${q ? "?" + q : ""}`);
    },
    get:   (id)       => _fetch(`/tiles/${id}`),
    patch: (id, body) => _fetch(`/tiles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  },
  satellites: {
    list:   (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/satellites${q ? "?" + q : ""}`);
    },
    get:    (id)       => _fetch(`/satellites/${id}`),
    create: (body)     => _fetch("/satellites", { method: "POST", body: JSON.stringify(body) }),
    patch:  (id, body) => _fetch(`/satellites/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id)       => _fetch(`/satellites/${id}`, { method: "DELETE" }),
    computePasses: (id, params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/satellites/${id}/compute-passes${q ? "?" + q : ""}`, { method: "POST" });
    },
    groundTrack: (id, params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/satellites/${id}/ground-track${q ? "?" + q : ""}`);
    },
    passStatus: (id) => _fetch(`/satellites/${id}/pass-status`),
  },
  passes: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/passes${q ? "?" + q : ""}`);
    },
  },
  orders: {
    list:   (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/orders${q ? "?" + q : ""}`);
    },
    get:    (id)       => _fetch(`/orders/${id}`),
    create: (body)     => _fetch("/orders", { method: "POST", body: JSON.stringify(body) }),
    patch:  (id, body) => _fetch(`/orders/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id)       => _fetch(`/orders/${id}`, { method: "DELETE" }),
  },
  stats: {
    coverage:      ()          => _fetch("/stats/coverage"),
    nextTargets:   (limit = 10) => _fetch(`/stats/next-targets?limit=${limit}`),
    opportunities: (limit = 20) => _fetch(`/stats/opportunities?limit=${limit}`),
  },
};

// ── Mock API ──────────────────────────────────────────────────────────────────

function _delay(ms = 80) { return new Promise((r) => setTimeout(r, ms)); }
function _deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }

let _satIdSeq = MOCK_SATELLITES.length + 1;

const MockAPI = {
  tiles: {
    list: async (params = {}) => {
      await _delay();
      let tiles = _deepClone(MOCK_TILES);
      if (params.is_land !== undefined)
        tiles = tiles.filter(t => t.is_land === (params.is_land === "true" || params.is_land === true));
      if (params.status) tiles = tiles.filter(t => t.status === params.status);
      return tiles;
    },
    get: async (id) => {
      await _delay();
      const t = MOCK_TILES.find(t => t.id === id);
      if (!t) throw new Error("Tile not found");
      return _deepClone(t);
    },
    patch: async (id, body) => {
      await _delay();
      const t = MOCK_TILES.find(t => t.id === id);
      if (!t) throw new Error("Tile not found");
      Object.assign(t, body);
      return _deepClone(t);
    },
  },
  satellites: {
    list: async (params = {}) => {
      await _delay();
      let sats = _deepClone(MOCK_SATELLITES);
      if (params.is_active !== undefined)
        sats = sats.filter(s => s.is_active === (params.is_active === "true" || params.is_active === true));
      return sats;
    },
    get: async (id) => {
      await _delay();
      const s = MOCK_SATELLITES.find(s => s.id === id);
      if (!s) throw new Error("Satellite not found");
      return _deepClone(s);
    },
    create: async (body) => {
      await _delay();
      const tileSize = (MOCK_TILES[0]?.tile_size ?? 10);
      const tileWidthKm = tileSize * 111;
      const warning = body.swath_width_km < tileWidthKm
        ? `Swath width ${body.swath_width_km} km is narrower than the tile grid (${tileSize}° ≈ ${tileWidthKm.toFixed(0)} km). A single pass will not cover a full tile.`
        : null;
      const sat = { id: _satIdSeq++, tle_epoch: null,
        tle_updated_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        tile_coverage_warning: warning,
        ...body };
      MOCK_SATELLITES.push(sat);
      return _deepClone(sat);
    },
    patch: async (id, body) => {
      await _delay();
      const s = MOCK_SATELLITES.find(s => s.id === id);
      if (!s) throw new Error("Satellite not found");
      Object.assign(s, body, { tle_updated_at: new Date().toISOString() });
      return _deepClone(s);
    },
    delete: async (id) => {
      await _delay();
      const idx = MOCK_SATELLITES.findIndex(s => s.id === id);
      if (idx === -1) throw new Error("Satellite not found");
      MOCK_SATELLITES.splice(idx, 1);
      return null;
    },
    computePasses: async (id, params = {}) => {
      await _delay(400); // simulate computation time
      const hours = Number(params.window_hours || 168);
      // Count passes for this satellite in the current MOCK_PASSES set
      const count = MOCK_PASSES.filter(p => p.satellite_id === id).length;
      return {
        satellite_id: id, window_hours: hours,
        tiles_checked: MOCK_TILES.filter(t => t.is_land && t.status === "NOT_STARTED").length,
        passes_found: count, elapsed_s: 0.42,
      };
    },
    passStatus: async (id) => {
      await _delay();
      const now = new Date();
      const satPasses = MOCK_PASSES.filter(p => p.satellite_id === id && new Date(p.pass_end) >= now);
      const latest = satPasses.reduce((max, p) =>
        !max || new Date(p.pass_end) > new Date(max) ? p.pass_end : max, null);
      return {
        satellite_id: id,
        passes_valid_until: latest || null,
        needs_recompute: !latest,
        pass_count: satPasses.length,
      };
    },
    groundTrack: async (id, params = {}) => {
      await _delay(100);
      const hours = Number(params.hours || 6);
      const stepS = Number(params.step_s || 120);
      const now = Date.now();
      const satIdx = (id - 1) % 3;
      const phaseOffset = satIdx * (Math.PI * 2 / 3);
      const period = 100 * 60 * 1000;
      const points = [];
      for (let s = 0; s < hours * 3600; s += stepS) {
        const t = (now + s * 1000) / period * 2 * Math.PI + phaseOffset;
        const lat = Math.sin(98.5 * Math.PI / 180) * 82 * Math.sin(t);
        const lon = ((s / (100 * 60) * 360 * (1 - 100 * 60 / 86400) + satIdx * 120) % 360 + 540) % 360 - 180;
        points.push({
          lat: Math.round(lat * 1000) / 1000,
          lon: Math.round(lon * 1000) / 1000,
          time: new Date(now + s * 1000).toISOString(),
        });
      }
      return points;
    },
  },
  passes: {
    list: async (params = {}) => {
      await _delay();
      const now = new Date();
      let passes = _deepClone(MOCK_PASSES).filter(p => new Date(p.pass_end) >= now);
      if (params.satellite_id !== undefined)
        passes = passes.filter(p => p.satellite_id === Number(params.satellite_id));
      if (params.tile_id !== undefined)
        passes = passes.filter(p => p.tile_id === Number(params.tile_id));
      return passes.slice(0, Number(params.limit || 200));
    },
  },
  orders: {
    list: async (params = {}) => {
      await _delay();
      let orders = _deepClone(MOCK_ORDERS);
      if (params.status) orders = orders.filter(o => o.status === params.status);
      if (params.tile_id !== undefined) orders = orders.filter(o => o.tile_id === Number(params.tile_id));
      if (params.satellite_id !== undefined) orders = orders.filter(o => o.satellite_id === Number(params.satellite_id));
      return orders.reverse();
    },
    get: async (id) => {
      await _delay();
      const o = MOCK_ORDERS.find(o => o.id === id);
      if (!o) throw new Error("Order not found");
      return _deepClone(o);
    },
    create: async (body) => {
      await _delay();
      const now = new Date().toISOString();
      const order = { id: _orderIdSeq++, status: "PLANNED",
        created_at: now, updated_at: now, completed_at: null, ...body };
      MOCK_ORDERS.push(order);
      if (body.tile_id) {
        const t = MOCK_TILES.find(t => t.id === body.tile_id);
        if (t && t.status === "NOT_STARTED") t.status = "IN_PROGRESS";
      }
      return _deepClone(order);
    },
    patch: async (id, body) => {
      await _delay();
      const o = MOCK_ORDERS.find(o => o.id === id);
      if (!o) throw new Error("Order not found");
      const now = new Date().toISOString();
      Object.assign(o, body, { updated_at: now });
      if (["COMPLETED","FAILED","CANCELLED"].includes(body.status) && !o.completed_at)
        o.completed_at = now;
      if (body.status === "COMPLETED" && o.tile_id) {
        const t = MOCK_TILES.find(t => t.id === o.tile_id);
        if (t) { t.status = "COMPLETED"; t.coverage_count += 1; t.last_captured_at = now; }
      }
      return _deepClone(o);
    },
    delete: async (id) => {
      await _delay();
      const idx = MOCK_ORDERS.findIndex(o => o.id === id);
      if (idx === -1) throw new Error("Order not found");
      MOCK_ORDERS.splice(idx, 1);
      return null;
    },
  },
  stats: {
    coverage: async () => {
      await _delay();
      const land = MOCK_TILES.filter(t => t.is_land);
      const completed = land.filter(t => t.status === "COMPLETED").length;
      const inProgress = land.filter(t => t.status === "IN_PROGRESS").length;
      const notStarted = land.filter(t => t.status === "NOT_STARTED").length;
      const byStatus = {};
      for (const o of MOCK_ORDERS) byStatus[o.status] = (byStatus[o.status] || 0) + 1;
      return {
        total_land_tiles: land.length, completed_tiles: completed,
        in_progress_tiles: inProgress, not_started_tiles: notStarted,
        coverage_pct: land.length ? Math.round(completed / land.length * 10000) / 100 : 0,
        total_orders: MOCK_ORDERS.length, orders_by_status: byStatus,
      };
    },
    nextTargets: async (limit = 10) => {
      await _delay();
      const now = new Date();
      // Sort by nearest upcoming pass
      const tileNextPass = {};
      for (const p of MOCK_PASSES) {
        if (new Date(p.pass_start) > now) {
          if (!tileNextPass[p.tile_id] || new Date(p.pass_start) < new Date(tileNextPass[p.tile_id]))
            tileNextPass[p.tile_id] = p.pass_start;
        }
      }
      return _deepClone(
        MOCK_TILES
          .filter(t => t.is_land && t.status === "NOT_STARTED")
          .sort((a, b) => {
            const pa = tileNextPass[a.id] ? new Date(tileNextPass[a.id]) : Infinity;
            const pb = tileNextPass[b.id] ? new Date(tileNextPass[b.id]) : Infinity;
            return pa - pb || Math.abs(a.center_lat) - Math.abs(b.center_lat);
          })
          .slice(0, limit)
      );
    },
    opportunities: async (limit = 20) => {
      await _delay();
      const now = new Date();
      const future = MOCK_PASSES
        .filter(p => new Date(p.pass_start) > now)
        .slice(0, limit);
      return future.map(p => {
        const tile = MOCK_TILES.find(t => t.id === p.tile_id);
        const sat = MOCK_SATELLITES.find(s => s.id === p.satellite_id);
        return { tile: _deepClone(tile), satellite: _deepClone(sat),
          pass_start: p.pass_start, pass_end: p.pass_end, duration_s: p.duration_s };
      }).filter(o => o.tile && o.satellite);
    },
  },
};

// ── Export single API surface ──────────────────────────────────────────────

const API = new Proxy({}, {
  get(_, section) {
    return (CONFIG.MOCK_MODE ? MockAPI : RealAPI)[section];
  },
});
