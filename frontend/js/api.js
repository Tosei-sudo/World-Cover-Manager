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
    get: (id) => _fetch(`/tiles/${id}`),
    patch: (id, body) => _fetch(`/tiles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  },
  orders: {
    list: (params = {}) => {
      const q = new URLSearchParams(params).toString();
      return _fetch(`/orders${q ? "?" + q : ""}`);
    },
    get: (id) => _fetch(`/orders/${id}`),
    create: (body) => _fetch("/orders", { method: "POST", body: JSON.stringify(body) }),
    patch: (id, body) => _fetch(`/orders/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
    delete: (id) => _fetch(`/orders/${id}`, { method: "DELETE" }),
  },
  stats: {
    coverage: () => _fetch("/stats/coverage"),
    nextTargets: (limit = 10) => _fetch(`/stats/next-targets?limit=${limit}`),
  },
};

// ── Mock API ──────────────────────────────────────────────────────────────────

function _delay(ms = 80) {
  return new Promise((r) => setTimeout(r, ms));
}

function _deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

const MockAPI = {
  tiles: {
    list: async (params = {}) => {
      await _delay();
      let tiles = _deepClone(MOCK_TILES);
      if (params.is_land !== undefined) tiles = tiles.filter((t) => t.is_land === (params.is_land === "true" || params.is_land === true));
      if (params.status) tiles = tiles.filter((t) => t.status === params.status);
      return tiles;
    },
    get: async (id) => {
      await _delay();
      const t = MOCK_TILES.find((t) => t.id === id);
      if (!t) throw new Error("Tile not found");
      return _deepClone(t);
    },
    patch: async (id, body) => {
      await _delay();
      const t = MOCK_TILES.find((t) => t.id === id);
      if (!t) throw new Error("Tile not found");
      Object.assign(t, body);
      return _deepClone(t);
    },
  },
  orders: {
    list: async (params = {}) => {
      await _delay();
      let orders = _deepClone(MOCK_ORDERS);
      if (params.status) orders = orders.filter((o) => o.status === params.status);
      if (params.tile_id !== undefined) orders = orders.filter((o) => o.tile_id === Number(params.tile_id));
      return orders.reverse();
    },
    get: async (id) => {
      await _delay();
      const o = MOCK_ORDERS.find((o) => o.id === id);
      if (!o) throw new Error("Order not found");
      return _deepClone(o);
    },
    create: async (body) => {
      await _delay();
      const now = new Date().toISOString();
      const order = {
        id: _orderIdSeq++,
        status: "PLANNED",
        created_at: now,
        updated_at: now,
        completed_at: null,
        ...body,
      };
      MOCK_ORDERS.push(order);
      // Mark parent tile IN_PROGRESS
      if (body.tile_id) {
        const t = MOCK_TILES.find((t) => t.id === body.tile_id);
        if (t && t.status === "NOT_STARTED") t.status = "IN_PROGRESS";
      }
      return _deepClone(order);
    },
    patch: async (id, body) => {
      await _delay();
      const o = MOCK_ORDERS.find((o) => o.id === id);
      if (!o) throw new Error("Order not found");
      const now = new Date().toISOString();
      Object.assign(o, body, { updated_at: now });
      const terminal = ["COMPLETED", "FAILED", "CANCELLED"];
      if (terminal.includes(body.status) && !o.completed_at) {
        o.completed_at = now;
      }
      // Propagate COMPLETED to tile
      if (body.status === "COMPLETED" && o.tile_id) {
        const t = MOCK_TILES.find((t) => t.id === o.tile_id);
        if (t) {
          t.status = "COMPLETED";
          t.coverage_count += 1;
          t.last_captured_at = now;
        }
      }
      return _deepClone(o);
    },
    delete: async (id) => {
      await _delay();
      const idx = MOCK_ORDERS.findIndex((o) => o.id === id);
      if (idx === -1) throw new Error("Order not found");
      MOCK_ORDERS.splice(idx, 1);
      return null;
    },
  },
  stats: {
    coverage: async () => {
      await _delay();
      const land = MOCK_TILES.filter((t) => t.is_land);
      const completed = land.filter((t) => t.status === "COMPLETED").length;
      const inProgress = land.filter((t) => t.status === "IN_PROGRESS").length;
      const notStarted = land.filter((t) => t.status === "NOT_STARTED").length;
      const byStatus = {};
      for (const o of MOCK_ORDERS) byStatus[o.status] = (byStatus[o.status] || 0) + 1;
      return {
        total_land_tiles: land.length,
        completed_tiles: completed,
        in_progress_tiles: inProgress,
        not_started_tiles: notStarted,
        coverage_pct: land.length ? Math.round((completed / land.length) * 10000) / 100 : 0,
        total_orders: MOCK_ORDERS.length,
        orders_by_status: byStatus,
      };
    },
    nextTargets: async (limit = 10) => {
      await _delay();
      return _deepClone(
        MOCK_TILES
          .filter((t) => t.is_land && t.status === "NOT_STARTED")
          .sort((a, b) => Math.abs(a.center_lat) - Math.abs(b.center_lat))
          .slice(0, limit)
      );
    },
  },
};

// ── Export single API surface ──────────────────────────────────────────────

const API = new Proxy({}, {
  get(_, section) {
    const impl = CONFIG.MOCK_MODE ? MockAPI : RealAPI;
    return impl[section];
  },
});
