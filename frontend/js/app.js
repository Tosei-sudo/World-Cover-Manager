/**
 * Main application controller.
 */

// ── State ─────────────────────────────────────────────────────────────────────

let _allTiles      = [];
let _allOrders     = [];
let _allSatellites = [];
let _currentView   = "map";

// ── Startup ───────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  _updateModeLabel();
  initMap();
  await Promise.all([refreshTiles(), refreshOrders(), refreshSatellites()]);
  await refreshStats();
  switchView("map");
});

function _updateModeLabel() {
  const el = document.getElementById("mode-badge");
  if (!el) return;
  el.textContent = CONFIG.MOCK_MODE ? "MOCK MODE" : "LIVE";
  el.classList.toggle("mock", CONFIG.MOCK_MODE);
}

// ── View switching ────────────────────────────────────────────────────────────

function switchView(view) {
  _currentView = view;
  ["map","table","orders","satellites","opportunities"].forEach(v => {
    document.getElementById(`view-${v}`)?.classList.toggle("active", v === view);
    document.getElementById(`btn-${v}`)?.classList.toggle("active", v === view);
  });
  if (view === "map") setTimeout(() => _map?.invalidateSize(), 50);
  if (view === "opportunities") loadOpportunities();
}

// ── Data refresh ──────────────────────────────────────────────────────────────

async function refreshTiles() {
  try {
    _allTiles = await API.tiles.list({ is_land: true });
    renderMapTiles(_allTiles);
    renderTileTable(_allTiles);
  } catch (e) { showError("Failed to load tiles: " + e.message); }
}

async function refreshOrders() {
  try {
    _allOrders = await API.orders.list();
    renderOrdersPanel(_allOrders);
  } catch (e) { showError("Failed to load orders: " + e.message); }
}

async function refreshSatellites() {
  try {
    _allSatellites = await API.satellites.list();
    renderSatellitesView(_allSatellites);
    _populateSatelliteSelect();
  } catch (e) { showError("Failed to load satellites: " + e.message); }
}

async function refreshStats() {
  try {
    const s = await API.stats.coverage();
    document.getElementById("stat-total").textContent      = s.total_land_tiles;
    document.getElementById("stat-completed").textContent  = s.completed_tiles;
    document.getElementById("stat-inprogress").textContent = s.in_progress_tiles;
    document.getElementById("stat-pct").textContent        = s.coverage_pct.toFixed(1) + "%";
    const bar = document.getElementById("coverage-bar-fill");
    if (bar) bar.style.width = s.coverage_pct + "%";
  } catch (e) { console.warn("Stats unavailable:", e); }
}

// ── Tile interaction ──────────────────────────────────────────────────────────

function onTileClick(tile) {
  const panel = document.getElementById("tile-detail");
  panel.innerHTML = `
    <button class="panel-close" onclick="closeTileDetail()" aria-label="Close">×</button>
    <h3>Tile #${tile.id}</h3>
    <table class="detail-table">
      <tr><td>Bounds</td><td>${tile.lat_min}°–${tile.lat_max}° N, ${tile.lon_min}°–${tile.lon_max}° E</td></tr>
      <tr><td>Centre</td><td>${tile.center_lat}°, ${tile.center_lon}°</td></tr>
      <tr><td>Status</td><td><span class="status-badge status-${tile.status.toLowerCase().replace("_","-")}">${tile.status.replace("_"," ")}</span></td></tr>
      <tr><td>Times covered</td><td>${tile.coverage_count}</td></tr>
      <tr><td>Last captured</td><td>${tile.last_captured_at ? new Date(tile.last_captured_at).toLocaleDateString() : "—"}</td></tr>
      ${tile.notes ? `<tr><td>Notes</td><td>${tile.notes}</td></tr>` : ""}
    </table>
    <div id="tile-passes-section" style="margin-bottom:10px"></div>
    <button class="btn btn-primary" onclick="openOrderForm(${tile.id}, ${tile.center_lat}, ${tile.center_lon})">
      + New Order for this tile
    </button>
  `;
  panel.classList.add("visible");
  _loadTilePasses(tile.id);
}

async function _loadTilePasses(tileId) {
  const sec = document.getElementById("tile-passes-section");
  if (!sec) return;
  try {
    const passes = await API.passes.list({ tile_id: tileId, limit: 5 });
    if (passes.length === 0) {
      sec.innerHTML = `<p style="font-size:12px;color:var(--text-muted)">No upcoming passes computed for this tile.</p>`;
      return;
    }
    sec.innerHTML = `
      <h4 style="font-size:13px;margin-bottom:6px">Upcoming passes (next ${passes.length})</h4>
      <table class="detail-table">
        ${passes.map(p => {
          const sat = _allSatellites.find(s => s.id === p.satellite_id);
          return `<tr>
            <td>${sat ? sat.name : "Sat #" + p.satellite_id}</td>
            <td>${fmtDateTime(p.pass_start)}<br><span style="color:var(--text-muted);font-size:11px">${p.duration_s}s</span></td>
            <td><button class="btn btn-xs btn-primary"
              onclick="openOrderFormFromPass(${tileId},${p.satellite_id},'${p.pass_start}','${p.pass_end}')">Order</button></td>
          </tr>`;
        }).join("")}
      </table>
    `;
  } catch (e) { sec.innerHTML = ""; }
}

function closeTileDetail() {
  document.getElementById("tile-detail").classList.remove("visible");
}

// ── Table view ────────────────────────────────────────────────────────────────

function renderTileTable(tiles) {
  const tbody = document.querySelector("#tile-table tbody");
  if (!tbody) return;
  tbody.innerHTML = tiles.map(t => `
    <tr onclick="onTileClick(${JSON.stringify(t).replace(/"/g,'&quot;')}); switchView('map');" style="cursor:pointer">
      <td>${t.id}</td>
      <td>${t.center_lat}°, ${t.center_lon}°</td>
      <td><span class="status-badge status-${t.status.toLowerCase().replace("_","-")}">${t.status.replace("_"," ")}</span></td>
      <td>${t.coverage_count}</td>
      <td>${t.last_captured_at ? new Date(t.last_captured_at).toLocaleDateString() : "—"}</td>
    </tr>
  `).join("");
}

function filterTable() {
  const q      = document.getElementById("table-filter").value.toLowerCase();
  const status = document.getElementById("table-status-filter").value;
  const filtered = _allTiles.filter(t => {
    const matchStatus = !status || t.status === status;
    const matchQ = !q || String(t.id).includes(q) ||
      String(t.center_lat).includes(q) || String(t.center_lon).includes(q);
    return matchStatus && matchQ;
  });
  renderTileTable(filtered);
}

// ── Orders panel ──────────────────────────────────────────────────────────────

function renderOrdersPanel(orders) {
  const container = document.getElementById("orders-list");
  if (!container) return;
  if (orders.length === 0) {
    container.innerHTML = "<p class='empty-msg'>No orders yet.</p>";
    return;
  }
  container.innerHTML = orders.map(o => {
    const sat = _allSatellites.find(s => s.id === o.satellite_id);
    return `
    <div class="order-card status-${o.status.toLowerCase().replace("_","-")}">
      <div class="order-card-header">
        <span class="order-id">#${o.id}</span>
        <span class="status-badge status-${o.status.toLowerCase().replace("_","-")}">${o.status.replace("_"," ")}</span>
        <span class="order-priority">P${o.priority}</span>
      </div>
      <div class="order-name">${o.target_name || `${o.center_lat}°, ${o.center_lon}°`}</div>
      ${sat ? `<div class="order-meta" style="color:#3b82f6">🛰 ${sat.name}</div>` : ""}
      <div class="order-meta">
        ${o.sensor_mode || "—"} · ${o.resolution_m ? o.resolution_m + " m" : "—"} · Cloud ≤${o.max_cloud_pct}%
      </div>
      ${o.scheduled_start ? `<div class="order-dates">${fmtDate(o.scheduled_start)} → ${fmtDate(o.scheduled_end)}</div>` : ""}
      <div class="order-actions">
        ${_progressButtons(o)}
        <button class="btn btn-sm btn-danger" onclick="deleteOrder(${o.id})">Delete</button>
      </div>
    </div>`;
  }).join("");
}

function _progressButtons(order) {
  const next = { PLANNED:"SCHEDULED", SCHEDULED:"IN_PROGRESS", IN_PROGRESS:"COMPLETED" }[order.status];
  const fail = ["PLANNED","SCHEDULED","IN_PROGRESS"].includes(order.status);
  return `
    ${next ? `<button class="btn btn-sm btn-success" onclick="advanceOrder(${order.id},'${next}')">→ ${next.replace("_"," ")}</button>` : ""}
    ${fail ? `<button class="btn btn-sm btn-warning" onclick="advanceOrder(${order.id},'FAILED')">FAILED</button>` : ""}
  `;
}

async function advanceOrder(id, newStatus) {
  try {
    await API.orders.patch(id, { status: newStatus });
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
  } catch (e) { showError("Failed to update order: " + e.message); }
}

async function deleteOrder(id) {
  if (!confirm("Delete this order?")) return;
  try {
    await API.orders.delete(id);
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
  } catch (e) { showError("Failed to delete order: " + e.message); }
}

// ── Satellites view ───────────────────────────────────────────────────────────

function renderSatellitesView(sats) {
  const container = document.getElementById("satellites-list");
  if (!container) return;
  if (sats.length === 0) {
    container.innerHTML = "<p class='empty-msg'>No satellites registered yet.</p>";
    return;
  }
  container.innerHTML = sats.map(s => `
    <div class="satellite-card${s.is_active ? "" : " inactive"}">
      <div class="sat-card-header">
        <span class="sat-name">${s.name}</span>
        ${s.norad_id ? `<span class="sat-norad">NORAD #${s.norad_id}</span>` : ""}
        <span class="status-badge ${s.is_active ? "status-completed" : "status-cancelled"}">${s.is_active ? "ACTIVE" : "INACTIVE"}</span>
      </div>
      <div class="sat-params">
        <span>Swath: <b>${s.swath_width_km} km</b></span>
        <span>Res: <b>${s.min_resolution_m ? s.min_resolution_m + " m" : "—"}</b></span>
        <span>Modes: <b>${s.sensor_modes || "—"}</b></span>
        <span>TLE epoch: <b>${s.tle_epoch ? new Date(s.tle_epoch).toLocaleDateString() : "—"}</b></span>
      </div>
      ${s.tile_coverage_warning ? `<div class="sat-swath-warning">⚠ ${s.tile_coverage_warning}</div>` : ""}
      <div id="sat-pass-status-${s.id}" class="sat-pass-status">
        <span class="pass-status-loading">Checking pass coverage…</span>
      </div>
      <div class="sat-tle">
        <code>${s.tle_line1.trim()}</code><br>
        <code>${s.tle_line2.trim()}</code>
      </div>
      ${s.notes ? `<div class="sat-notes">${s.notes}</div>` : ""}
      <div class="sat-actions">
        <button class="btn btn-sm btn-secondary" id="btn-recompute-${s.id}" onclick="computePasses(${s.id}, this)">Recompute now</button>
        <button class="btn btn-sm btn-secondary" onclick="showGroundTrack(${s.id})">Show track</button>
        <button class="btn btn-sm btn-secondary" onclick="openSatelliteEditForm(${s.id})">Edit TLE</button>
        <button class="btn btn-sm btn-danger" onclick="deleteSatellite(${s.id})">Delete</button>
      </div>
      <div id="sat-compute-result-${s.id}" class="sat-compute-result"></div>
    </div>
  `).join("");

  // Load pass status for each satellite asynchronously
  for (const s of sats) {
    if (s.is_active) _refreshPassStatus(s.id);
  }
}

async function _refreshPassStatus(satId) {
  const el = document.getElementById(`sat-pass-status-${satId}`);
  if (!el) return;
  try {
    const s = await API.satellites.passStatus(satId);
    if (s.needs_recompute && !s.passes_valid_until) {
      el.innerHTML = `<span class="pass-status-stale">No passes computed — will auto-compute on next query</span>`;
    } else if (s.needs_recompute) {
      el.innerHTML = `<span class="pass-status-stale">⚠ Passes expiring soon · valid until ${fmtDateTime(s.passes_valid_until)} · ${s.pass_count} remaining</span>`;
    } else {
      el.innerHTML = `<span class="pass-status-ok">✓ ${s.pass_count} passes · valid until ${fmtDateTime(s.passes_valid_until)}</span>`;
    }
  } catch (_) {
    el.innerHTML = "";
  }
}

async function computePasses(satId, btn) {
  const resultEl = document.getElementById(`sat-compute-result-${satId}`);
  btn.disabled = true;
  btn.textContent = "Computing…";
  if (resultEl) resultEl.textContent = "";
  try {
    const r = await API.satellites.computePasses(satId, { window_hours: 168, step_s: 60 });
    if (resultEl)
      resultEl.innerHTML = `<span style="color:var(--success)">✓ ${r.passes_found} passes found over ${r.tiles_checked} tiles (${r.elapsed_s}s)</span>`;
    await Promise.all([refreshStats(), _refreshPassStatus(satId)]);
  } catch (e) {
    if (resultEl) resultEl.innerHTML = `<span style="color:var(--danger)">${e.message}</span>`;
    showError("Pass computation failed: " + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Recompute now";
  }
}

async function showGroundTrack(satId) {
  const sat = _allSatellites.find(s => s.id === satId);
  if (!sat) return;
  try {
    const pts = await API.satellites.groundTrack(satId, { hours: 6, step_s: 120 });
    drawGroundTrack(satId, sat.name, pts, sat.swath_width_km);
    switchView("map");
    showInfo(`Showing 6-hour ground track for ${sat.name}`);
  } catch (e) { showError("Failed to load ground track: " + e.message); }
}

async function deleteSatellite(id) {
  if (!confirm("Delete this satellite and all its computed passes?")) return;
  try {
    await API.satellites.delete(id);
    await refreshSatellites();
  } catch (e) { showError("Failed to delete satellite: " + e.message); }
}

// ── Satellite form ────────────────────────────────────────────────────────────

function openSatelliteForm(satId = null) {
  const sat  = satId ? _allSatellites.find(s => s.id === satId) : null;
  const form = document.getElementById("satellite-form-panel");
  const title = document.getElementById("sf-title");

  title.textContent = sat ? "Edit Satellite" : "Add Satellite";
  document.getElementById("sf-id").value          = sat ? sat.id : "";
  document.getElementById("sf-name").value        = sat ? sat.name : "";
  document.getElementById("sf-norad").value       = sat ? (sat.norad_id ?? "") : "";
  document.getElementById("sf-swath").value       = sat ? sat.swath_width_km : "";
  document.getElementById("sf-resolution").value  = sat ? (sat.min_resolution_m ?? "") : "";
  document.getElementById("sf-modes").value       = sat ? (sat.sensor_modes ?? "") : "";
  document.getElementById("sf-notes").value       = sat ? (sat.notes ?? "") : "";

  // Pre-fill TLE block
  const tlePre = sat ? `${sat.name}\n${sat.tle_line1}\n${sat.tle_line2}` : "";
  document.getElementById("sf-tle").value = tlePre;

  form.classList.add("visible");
}

function openSatelliteEditForm(satId) { openSatelliteForm(satId); }

function closeSatelliteForm() {
  document.getElementById("satellite-form-panel").classList.remove("visible");
}

function _parseTLEBlock(text) {
  const lines = text.trim().split("\n").map(l => l.trim()).filter(Boolean);
  if (lines.length === 3 && lines[1].startsWith("1 ") && lines[2].startsWith("2 "))
    return { name_hint: lines[0], line1: lines[1], line2: lines[2] };
  if (lines.length === 2 && lines[0].startsWith("1 ") && lines[1].startsWith("2 "))
    return { name_hint: null, line1: lines[0], line2: lines[1] };
  throw new Error("Paste a 2- or 3-line TLE block (copy from Celestrak).");
}

async function submitSatelliteForm(e) {
  e.preventDefault();
  const satId  = document.getElementById("sf-id").value;
  const tleRaw = document.getElementById("sf-tle").value;

  let tle;
  try { tle = _parseTLEBlock(tleRaw); }
  catch (err) { showError(err.message); return; }

  const nameEl = document.getElementById("sf-name").value.trim();
  const body = {
    name:           nameEl || tle.name_hint || "Unknown",
    norad_id:       Number(document.getElementById("sf-norad").value) || null,
    tle_line1:      tle.line1,
    tle_line2:      tle.line2,
    swath_width_km: Number(document.getElementById("sf-swath").value),
    min_resolution_m: Number(document.getElementById("sf-resolution").value) || null,
    sensor_modes:   document.getElementById("sf-modes").value || null,
    is_active:      true,
    notes:          document.getElementById("sf-notes").value || null,
  };

  try {
    if (satId) {
      await API.satellites.patch(Number(satId), body);
    } else {
      await API.satellites.create(body);
    }
    closeSatelliteForm();
    await refreshSatellites();
    switchView("satellites");
  } catch (e) { showError("Failed to save satellite: " + e.message); }
}

// ── Opportunities view ────────────────────────────────────────────────────────

async function loadOpportunities() {
  const container = document.getElementById("opportunities-list");
  if (!container) return;
  container.innerHTML = `<p class="empty-msg">Loading…</p>`;
  try {
    const ops = await API.stats.opportunities(30);
    if (ops.length === 0) {
      container.innerHTML = `<p class="empty-msg">No upcoming passes found for uncovered tiles. Passes are computed automatically — check that at least one active satellite with a valid TLE is registered.</p>`;
      return;
    }
    container.innerHTML = ops.map((op, i) => `
      <div class="opportunity-card">
        <div class="opp-rank">#${i + 1}</div>
        <div class="opp-main">
          <div class="opp-sat">${op.satellite.name}</div>
          <div class="opp-tile">Tile #${op.tile.id} &nbsp; ${op.tile.center_lat}°, ${op.tile.center_lon}°</div>
          <div class="opp-time">
            ${fmtDateTime(op.pass_start)}
            <span class="opp-dur">${op.duration_s}s</span>
          </div>
        </div>
        <div class="opp-actions">
          <button class="btn btn-sm btn-primary"
            onclick="openOrderFormFromPass(${op.tile.id}, ${op.satellite.id}, '${op.pass_start}', '${op.pass_end}', ${op.tile.center_lat}, ${op.tile.center_lon})">
            Create Order
          </button>
        </div>
      </div>
    `).join("");
  } catch (e) { container.innerHTML = `<p class="empty-msg" style="color:var(--danger)">${e.message}</p>`; }
}

// ── Next targets (legacy panel) ───────────────────────────────────────────────

async function showNextTargets() {
  const panel = document.getElementById("next-targets-panel");
  try {
    const targets = await API.stats.nextTargets(10);
    panel.innerHTML = `
      <button class="panel-close" onclick="closeNextTargets()" aria-label="Close">×</button>
      <h4>Suggested Next Targets</h4>
      <ul>
        ${targets.map(t => `
          <li>
            Tile #${t.id} – (${t.center_lat}°, ${t.center_lon}°)
            <button class="btn btn-xs btn-primary" onclick="openOrderForm(${t.id}, ${t.center_lat}, ${t.center_lon})">Order</button>
          </li>
        `).join("")}
      </ul>
    `;
    panel.classList.add("visible");
  } catch (e) { showError("Failed to load suggestions: " + e.message); }
}

function closeNextTargets() {
  document.getElementById("next-targets-panel").classList.remove("visible");
}

// ── Order form ────────────────────────────────────────────────────────────────

function _populateSatelliteSelect() {
  const sel = document.getElementById("of-satellite");
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="">— none —</option>` +
    _allSatellites.filter(s => s.is_active).map(s =>
      `<option value="${s.id}">${s.name}</option>`
    ).join("");
  if (current) sel.value = current;
}

function openOrderForm(tileId = null, lat = 0, lon = 0) {
  _resetOrderForm();
  document.getElementById("of-tile-id").value = tileId ?? "";
  document.getElementById("of-lat").value = lat;
  document.getElementById("of-lon").value = lon;
  document.getElementById("of-name").value = tileId ? `Tile #${tileId}` : "";
  document.getElementById("order-form-panel").classList.add("visible");
  closeTileDetail();
  closeNextTargets();
}

function openOrderFormFromPass(tileId, satId, passStart, passEnd, lat = null, lon = null) {
  _resetOrderForm();
  const tile = _allTiles.find(t => t.id === tileId);
  document.getElementById("of-tile-id").value    = tileId;
  document.getElementById("of-satellite").value  = satId;
  document.getElementById("of-lat").value        = lat ?? tile?.center_lat ?? 0;
  document.getElementById("of-lon").value        = lon ?? tile?.center_lon ?? 0;
  document.getElementById("of-name").value       = tile ? `Tile #${tile.id}` : "";
  // Format datetime-local from ISO string
  document.getElementById("of-start").value = passStart ? passStart.slice(0,16) : "";
  document.getElementById("of-end").value   = passEnd   ? passEnd.slice(0,16)   : "";
  // Pre-fill sensor mode from satellite
  const sat = _allSatellites.find(s => s.id === satId);
  if (sat?.sensor_modes) {
    const firstMode = sat.sensor_modes.split(",")[0].trim();
    document.getElementById("of-sensor").value = firstMode;
  }
  document.getElementById("order-form-panel").classList.add("visible");
  closeTileDetail();
}

function _resetOrderForm() {
  ["of-tile-id","of-lat","of-lon","of-name","of-start","of-end",
   "of-res","of-sun","of-nadir","of-notes"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  document.getElementById("of-cloud").value    = "20";
  document.getElementById("of-priority").value = "5";
  document.getElementById("of-sensor").value   = "";
  document.getElementById("of-satellite").value = "";
}

function closeOrderForm() {
  document.getElementById("order-form-panel").classList.remove("visible");
}

async function submitOrderForm(e) {
  e.preventDefault();
  const tileId = document.getElementById("of-tile-id").value;
  const satId  = document.getElementById("of-satellite").value;
  const body = {
    tile_id:       tileId ? Number(tileId) : null,
    satellite_id:  satId  ? Number(satId)  : null,
    center_lat:    Number(document.getElementById("of-lat").value),
    center_lon:    Number(document.getElementById("of-lon").value),
    target_name:   document.getElementById("of-name").value || null,
    scheduled_start: document.getElementById("of-start").value || null,
    scheduled_end:   document.getElementById("of-end").value || null,
    sensor_mode:   document.getElementById("of-sensor").value || null,
    resolution_m:  Number(document.getElementById("of-res").value) || null,
    max_cloud_pct: Number(document.getElementById("of-cloud").value) || 20,
    sun_elev_min:  Number(document.getElementById("of-sun").value) || null,
    off_nadir_max: Number(document.getElementById("of-nadir").value) || null,
    priority:      Number(document.getElementById("of-priority").value) || 5,
    notes:         document.getElementById("of-notes").value || null,
  };
  try {
    await API.orders.create(body);
    closeOrderForm();
    await Promise.all([refreshTiles(), refreshOrders(), refreshStats()]);
    switchView("orders");
  } catch (e) { showError("Failed to create order: " + e.message); }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month:"short", day:"numeric", year:"numeric" });
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit", timeZoneName:"short" });
}

function showError(msg) {
  const el = document.getElementById("error-toast");
  el.textContent = msg;
  el.style.background = "#1f2937";
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 5000);
}

function showInfo(msg) {
  const el = document.getElementById("error-toast");
  el.textContent = msg;
  el.style.background = "#0f766e";
  el.classList.add("visible");
  setTimeout(() => el.classList.remove("visible"), 3000);
}
