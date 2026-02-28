export async function logEvent(event, data = {}) {
  try {
    await fetch("http://127.0.0.1:8001/api/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, data }),
    });
  } catch (e) {
    console.warn("Failed to log event:", e);
  }
}
