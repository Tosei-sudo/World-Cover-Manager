/**
 * Global configuration.
 * Set MOCK_MODE = true to run entirely in the browser with no backend.
 * Set MOCK_MODE = false (default) to talk to the real FastAPI server.
 */
const CONFIG = {
  MOCK_MODE: false,          // ← toggle here, or via ?mock=1 in the URL
  API_BASE: "/api",          // base URL for the real API
  TILE_SIZE_DEG: 10,         // must match the value used in init_db.py
};

// Allow ?mock=1 in the URL to force mock mode without editing this file
if (new URLSearchParams(window.location.search).get("mock") === "1") {
  CONFIG.MOCK_MODE = true;
}
