// api.config.js
// ─────────────────────────────────────────────────────────────────
// Backend is deployed on Render — works from anywhere!
// No more IP address changes needed ✅
// ─────────────────────────────────────────────────────────────────

const RENDER_URL = "https://mail-mind-ai.onrender.com";

const isCapacitor = typeof window !== "undefined" &&
                    window.Capacitor !== undefined;

const isLocalDev  = !isCapacitor && (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
);

// Local dev → use local backend
// Phone app → use Render cloud backend
// Any other → use Render cloud backend
export const API_BASE = isLocalDev
  ? "http://localhost:5000/api"
  : `${RENDER_URL}/api`;

export default API_BASE;