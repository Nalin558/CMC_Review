// src/logService.js
import axios from "axios";

const API_BASE = "http://127.0.0.1:8001";   // backend

// generate unique session ID per webpage load
const sessionId = "sess_" + Math.random().toString(36).substring(2, 12);

export function getSessionId() {
  return sessionId;
}

export async function logEvent(eventType, payload = {}) {
  try {
    await axios.post(`${API_BASE}/log/event`, {
      session_id: sessionId,
      event_type: eventType,
      timestamp: new Date().toISOString(),
      payload
    });
  } catch (err) {
    console.error("Failed to send log:", err);
  }
}
