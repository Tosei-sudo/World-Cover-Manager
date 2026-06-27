/**
 * Global configuration.
 * Set MOCK_MODE = true to run entirely in the browser with no backend.
 * Set MOCK_MODE = false (default) to talk to the real FastAPI server.
 *
 * TILE_SERVER_URL: URL template for the background map tile server.
 *   Use "{s}.tile.openstreetmap.org" only when internet access is available.
 *   For closed networks, point to an internal tile server (XYZ format) or
 *   set to null to disable the background map entirely.
 */
const CONFIG = {
  MOCK_MODE: false,          // ← toggle here, or via ?mock=1 in the URL
  API_BASE: "/api",          // base URL for the real API
  TILE_SIZE_DEG: 10,         // must match the value used in init_db.py

  // Background map tile server URL template (XYZ / slippy-map format).
  // null = plain background (no tile layer); suits air-gapped environments.
  TILE_SERVER_URL: null,
  TILE_ATTRIBUTION: "",
};

// Allow ?mock=1 in the URL to force mock mode without editing this file
if (new URLSearchParams(window.location.search).get("mock") === "1") {
  CONFIG.MOCK_MODE = true;
}
