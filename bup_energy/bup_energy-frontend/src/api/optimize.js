// Thin wrapper around Django's POST /optimize-energy.
// Vite proxies /api -> http://localhost:8000 (see vite.config.js).

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

export async function postOptimize(payload) {
  let response;
  try {
    response = await fetch(`${API_BASE}/optimize-energy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (networkError) {
    const err = new Error(
      "Could not reach the optimizer server. Is Django running on http://localhost:8000?"
    );
    err.cause = networkError;
    throw err;
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON response (very rare); fall through with status code only.
  }

  if (!response.ok) {
    const message = body?.error || `Request failed with status ${response.status}`;
    const err = new Error(message);
    err.status = response.status;
    err.server = body?.server;
    throw err;
  }

  return body;
}
