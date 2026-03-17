// Capacitor apps run on localhost too!
// So we need a different way to detect mobile

const YOUR_PC_IP = "192.168.1.100";
// Check if running in Capacitor (mobile app)
const isCapacitor = window.Capacitor !== undefined || 
                    window.location.protocol === "capacitor:";

// Check if regular web browser
const isWeb = !isCapacitor && (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
);

export const API_BASE = isWeb
  ? "http://localhost:5000/api"          // laptop browser
  : `http://${YOUR_PC_IP}:5000/api`;     // phone app

export default API_BASE;