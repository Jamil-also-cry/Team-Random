// Thin wrapper around the Django DRF endpoint POST /optimize-energy.
//
// Vite dev server proxies /api -> http://localhost:8000 (see vite.config.js).
// In production builds, set VITE_API_BASE to the absolute Django origin.

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const SERVER_LABEL = "SuryaGrid (Django)";

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
    // Django/DRF returns {"detail": "..."} on errors.
    const message =
      body?.detail || `Request failed with status ${response.status}`;
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  return normalizeResponse(body, payload);
}

// The Django view returns the canonical pydantic OptimizeResponse:
// { scenario_id, directive_interpretation[], hourly_plan[], total_grid_kwh,
//   total_cost_bdt, peak_grid_kwh, plan_summary }
// The React UI was originally built against the legacy mock shape with a
// nested `summary` object and a `server` pill. We rebuild that summary
// from `hourly_plan` so the existing SummaryCards component keeps working.
function normalizeResponse(raw, requestPayload) {
  const plan = Array.isArray(raw.hourly_plan) ? raw.hourly_plan : [];
  const battery = requestPayload?.battery ?? {};

  let total_grid_kwh = Number(raw.total_grid_kwh ?? 0);
  let total_cost_bdt = Number(raw.total_cost_bdt ?? 0);
  let peak_grid_kwh = Number(raw.peak_grid_kwh ?? 0);

  let solar_used_total = 0;
  let solar_curtailed_total = 0;
  let battery_charged_total = 0;
  let battery_discharged_total = 0;

  for (const row of plan) {
    solar_used_total += Number(row.solar_used_kwh ?? 0);
    solar_curtailed_total += Math.max(
      0,
      Number(row.solar_kwh ?? 0) - Number(row.solar_used_kwh ?? 0)
    );
    if (row.battery_action === "charge") {
      battery_charged_total += Number(row.battery_kwh ?? 0);
    } else if (row.battery_action === "discharge") {
      battery_discharged_total += Number(row.battery_kwh ?? 0);
    }
  }

  if (!raw.total_grid_kwh) {
    total_grid_kwh = plan.reduce((s, r) => s + Number(r.grid_kwh ?? 0), 0);
  }
  if (!raw.total_cost_bdt) {
    total_cost_bdt = plan.reduce(
      (s, r) => s + Number(r.grid_kwh ?? 0) * Number(r.tariff_bdt_per_kwh ?? 0),
      0
    );
  }
  if (!raw.peak_grid_kwh) {
    peak_grid_kwh = plan.reduce(
      (max, r) => Math.max(max, Number(r.grid_kwh ?? 0)),
      0
    );
  }

  const initial_battery_kwh = Number(battery.initial_energy_kwh ?? 0);
  const final_battery_kwh = plan.length
    ? Number(plan[plan.length - 1].battery_energy_after_kwh ?? initial_battery_kwh)
    : initial_battery_kwh;
  const neutrality_delta_kwh = Number(
    (final_battery_kwh - initial_battery_kwh).toFixed(3)
  );

  return {
    scenario_id: raw.scenario_id,
    server: SERVER_LABEL,
    directive_interpretation: raw.directive_interpretation ?? [],
    hourly_plan: plan,
    plan_summary: raw.plan_summary ?? "",
    summary: {
      total_grid_kwh: round2(total_grid_kwh),
      total_cost_bdt: round2(total_cost_bdt),
      peak_grid_kwh: round2(peak_grid_kwh),
      solar_used_total: round2(solar_used_total),
      solar_curtailed_total: round2(solar_curtailed_total),
      battery_charged_total: round2(battery_charged_total),
      battery_discharged_total: round2(battery_discharged_total),
      initial_battery_kwh: round2(initial_battery_kwh),
      final_battery_kwh: round2(final_battery_kwh),
      neutrality_delta_kwh,
    },
  };
}

function round2(n) {
  return Math.round(Number(n || 0) * 100) / 100;
}

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return { ok: false, status: res.status };
    const body = await res.json();
    return { ok: body?.status === "ok", status: res.status };
  } catch {
    return { ok: false, status: 0 };
  }
}
