/**
 * Main application controller.
 * Wires together the map, table, orders panel, and stats bar.
 */

// ── State ─────────────────────────────────────────────────────────────────────

let _allTiles = [];
let _allOrders = [];
let _currentView = "map";  // "map" | "table" | "orders"

// ── Startup ───────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  _updateModeLabel();
  initMap();
  await Promise.all([refreshTiles(), refreshOrders()]);
  await refreshStats();
  switchView("map");
});

// ── Mode label ────────────────────────────────────────────────────────────────

function _updateModeLabel() {
  const el = document.getElementById("mode-badge");
  if (!el) return;
  if (CONFIG.MOCK_MODE) {
    el.textContent = "MOCK MODE";
    el.classList.add("mock");
  } else {
    el.textContent = "LIVE";
    el.classList.remove("mock");
  }
}

// ── View switching ────────────────────────────────────────────────────────────

function switchView(view) {
  _currentView = view;
  ["map", "table", "orders"].forEach((v) => {
    document.getElementById(`view-${v}`).classList.toggle("active", v === view);
    document.getElementById(`btn-${v}`).classList.toggle("active", v === view);
  });
  if (view === "map") {
    // Leaflet needs a size recalc after being hidden
    setTimeout(() => _map && _map.invalidateSize(), 50);
  }
}

// ── Data refresh ──────────────────────────────────────────────────────────────

async function refreshTiles() {
  try {
    _allTiles = await API.tiles.list({ is_land: true });
    renderMapTiles(_allTiles);
    renderTileTable(_allTiles);
  } catch (e) {
    showError("Failed to load tiles: " + e.message);
  }
}

async function refreshOrders() {
  try {
    _allOrders = await API.orders.list();
    renderOrdersPanel(_allOrders);
  } catch (e) {
    showError("Failed to load orders: " + e.message);
  }
}

async function refreshStats() {
  try {
    const s = await API.stats.coverage();
    document.getElementById("stat-total").textContent = s.total_land_tiles;
    document.getElementById("stat-completed").textContent = s.completed_tiles;
    document.getElementById("stat-inprogress").textContent = s.in_progress_tiles;
    document.getElementById("stat-pct").textContent = s.coverage_pct.toFixed(1) + "%";
    const bar = document.getElementById("coverage-bar-fill");
    if (bar) bar.style.width = s.coverage_pct + "%";
  } catch (e) {
    console.warn("Stats unavailable:", e);
  }
}

// ── Tile click ────────────────────────────────────────────────────────────────

function onTileClick(tile) {
  const panel = document.getElementById("tile-detail");
  panel.innerHTML = `
    <h3>Tile #${tile.id}</h3>
    <table class="detail-table">
      <tr><td>Bounds</td><td>${tile.lat_min}°–${tile.lat_max}° N, ${tile.lon_min}°–${tile.lon_max}° E</td></tr>
      <tr><td>Centre</td><td>${tile.center_lat}°, ${tile.center_lon}°</td></tr>
      <tr><td>Status</td><td><span class="status-badge status-${tile.status.toLowerCase().replace("_","-")}">${tile.status.replace("_"," ")}</span></td></tr>
      <tr><td>Times covered</td><td>${tile.coverage_count}</td></tr>
      <tr><td>Last captured</td><td>${tile.last_captured_at ? new Date(tile.last_captured_at).toLocaleDateString() : "—"}</td></tr>
      ${tile.notes ? `<tr><td>Notes</td><td>${tile.notes}</td></tr>` : ""}
    </table>
    <button class="btn btn-primary" onclick="openOrderForm(${tile.id}, ${tile.center_lat}, ${tile.center_lon})">
      + New Order for this tile
    </button>
  `;
  panel.classList.add("visible");
}

function closeTileDetail() {
  document.getElementById("tile-detail").classList.remove("visible");
}

// ── Table view ────────────────────────────────────────────────────────────────

function renderTileTable(tiles) {
  const tbody = document.querySelector("#tile-table tbody");
  if (!tbody) return;
  tbody.innerHTML = tiles.map((t) => `
    <tr onclick="onTileClick(${JSON.stringify(t).replace(/"/g, '&quot;')}); switchView('map');" style="cursor:pointer">
      <td>${t.id}</td>
      <td>${t.center_lat}°, ${t.center_lon}°</td>
      <td><span class="status-badge status-${t.status.toLowerCase().replace("_","-")}">${t.status.replace("_"," ")}</span></td>
      <td>${t.coverage_count}</td>
      <td>${t.last_captured_at ? new Date(t.last_captured_at).toLocaleDateString() : "—"}</td>
    </tr>
  `).join("");
}

function filterTable() {
  const q = document.getElementById("table-filter").value.toLowerCase();
  const status = document.getElementById("table-status-filter").value;
  const filtered = _allTiles.filter((t) => {
    const matchStatus = !status || t.status === status;
    const matchQ = !q || String(t.id).includes(q) ||
      String(t.center_lat).includes(q) || String(t.center_lon).includes(q);
    return matchStatus && matchQ;
  });
  renderTileTable(filtered);
}

// ── Orders panel ──────────────────────────────────────────────────────────────

const ORDER_STATUS_STEPS = ["PLANNED", "SCHEDULED", "IN_PROGRESS", "COMPLETED"];

function renderOrdersPanel(orders) {
  const container = document.getElementById("orders-list");
  if (!container) return;
  if (orders.length === 0) {
    container.innerHTML = "<p class='empty-msg'>No orders yet.</p>";
    return;
  }
  container.innerHTML = orders.map((o) => `
    <div class="order-card status-${o.status.toLowerCase().replace("_","-")}">
      <div class="order-card-header">
        <span class="order-id">#${o.id}</span>
        <span class="status-badge status-${o.status.toLowerCase().replace("_","-")}">${o.status.replace("_"," ")}</span>
        <span class="order-priority">P${o.priority}</span>
      </div>
      <div class="order-name">${o.target_name || `${o.center_lat}°, ${o.center_lon}°`}</div>
      <div class="order-meta">
        ${o.sensor_mode || "—"} · ${o.resolution_m ? o.resolution_m + " m" : "—"} ·
        Cloud &le;${o.max_cloud_pct}%
      </div>
      ${o.scheduled_start ? `<div class="order-dates">${fmtDate(o.scheduled_start)} → ${fmtDate(o.scheduled_end)}</div>` : ""}
      <div class="order-actions">
        ${_progressButtons(o)}
        <button class="btn btn-sm btn-danger" onclick="deleteOrder(${o.id})">Delete</button>
      </div>
    </div>
  `).join("");
}

function _progressButtons(order) {
  const next = {
    PLANNED: "SCHEDULED",
    SCHEDULED: "IN_PROGRESS",
    IN_PROGRESS: "COMPLETED",
  }[order.status];
  const fail = ["PLANNED","SCHEDULED","IN_PROGRESS"].includes(order.status);
  return `
    ${next ? `<button class="btn btn-sm btn-success" onclick="advanceOrder(${order.id}, '${next}')">→ ${next.replace("_"," ")}</button>` : ""}
    ${fail ? `<button class="btn btn-sm btn-warning" onclick="advanceOrder(${order.id}, 'FAILED')">Mark FAILED</button>` : ""}
  `;
}

async function advanceOrder(id, newStatus) {
  try {
    await API.orders.patch(id, { status: newStatus });
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
  } catch (e) {
    showError("Failed to update order: " + e.message);
  }
}

async function deleteOrder(id) {
  if (!confirm("Delete this order?")) return;
  try {
    await API.orders.delete(id);
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
  } catch (e) {
    showError("Failed to delete order: " + e.message);
  }
}

// ── Next-targets suggestion ───────────────────────────────────────────────────

async function showNextTargets() {
  const panel = document.getElementById("next-targets-panel");
  try {
    const targets = await API.stats.nextTargets(10);
    panel.innerHTML = `
      <h4>Suggested Next Targets</h4>
      <ul>
        ${targets.map((t) => `
          <li>
            Tile #${t.id} – (${t.center_lat}°, ${t.center_lon}°)
            <button class="btn btn-xs btn-primary" onclick="openOrderForm(${t.id}, ${t.center_lat}, ${t.center_lon})">Order</button>
          </li>
        `).join("")}
      </ul>
    `;
    panel.classList.add("visible");
  } catch (e) {
    showError("Failed to load suggestions: " + e.message);
  }
}

function closeNextTargets() {
  document.getElementById("next-targets-panel").classList.remove("visible");
}

// ── Order form ────────────────────────────────────────────────────────────────

function openOrderForm(tileId = null, lat = 0, lon = 0) {
  const form = document.getElementById("order-form-panel");
  document.getElementById("of-tile-id").value = tileId ?? "";
  document.getElementById("of-lat").value = lat;
  document.getElementById("of-lon").value = lon;
  document.getElementById("of-name").value = tileId ? `Tile #${tileId}` : "";
  form.classList.add("visible");
  closeTileDetail();
  closeNextTargets();
}

function closeOrderForm() {
  document.getElementById("order-form-panel").classList.remove("visible");
}

async function submitOrderForm(e) {
  e.preventDefault();
  const tileId = document.getElementById("of-tile-id").value;
  const body = {
    tile_id: tileId ? Number(tileId) : null,
    center_lat: Number(document.getElementById("of-lat").value),
    center_lon: Number(document.getElementById("of-lon").value),
    target_name: document.getElementById("of-name").value || null,
    scheduled_start: document.getElementById("of-start").value || null,
    scheduled_end: document.getElementById("of-end").value || null,
    sensor_mode: document.getElementById("of-sensor").value || null,
    resolution_m: Number(document.getElementById("of-res").value) || null,
    max_cloud_pct: Number(document.getElementById("of-cloud").value) || 20,
    sun_elev_min: Number(document.getElementById("of-sun").value) || null,
    off_nadir_max: Number(document.getElementById("of-nadir").value) || null,
    priority: Number(document.getElementById("of-priority").value) || 5,
    notes: document.getElementById("of-notes").value || null,
  };
  try {
    await API.orders.create(body);
    closeOrderForm();
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
    switchView("orders");
  } catch (e) {
    showError("Failed to create order: " + e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function showError(msg) {
  const el = document.getElementById("error-toast");
  el.textContent = msg;
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 5000);
}
