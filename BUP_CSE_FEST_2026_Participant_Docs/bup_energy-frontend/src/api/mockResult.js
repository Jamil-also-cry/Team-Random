// Mock optimizer response used until the user approves the design.
// Shape matches the real POST /optimize-energy response.

export function getMockResult() {
  const hours = Array.from({ length: 24 }, (_, h) => {
    const demand = 8 + Math.sin((h - 6) / 24 * Math.PI * 2) * 4 + (h >= 18 && h <= 22 ? 6 : 0);
    const solar = h >= 6 && h <= 18 ? Math.max(0, Math.sin(((h - 6) / 12) * Math.PI) * 12) : 0;
    const tariff = h >= 17 && h <= 22 ? 18 : h >= 0 && h <= 5 ? 9 : 12;
    const solar_used = Math.min(solar, demand);
    const remaining = Math.max(demand - solar_used, 0);
    const grid = Number((remaining + (tariff < 12 ? 2 : 0)).toFixed(2));
    const discharge = tariff > 14 && remaining > 0 ? Math.min(remaining, 4) : 0;
    return {
      hour: h,
      demand_kwh: Number(demand.toFixed(2)),
      solar_kwh: Number(solar.toFixed(2)),
      solar_used_kwh: Number(solar_used.toFixed(2)),
      tariff_bdt_per_kwh: tariff,
      grid_kwh: Number((grid - discharge).toFixed(2)),
      battery_action: discharge > 0 ? "discharge" : solar > demand ? "charge" : "idle",
      battery_kwh: Number(discharge.toFixed(2)),
      battery_charge_kwh: 0,
      battery_discharge_kwh: Number(discharge.toFixed(2)),
      battery_energy_after_kwh: Number((50 + h * 0.2).toFixed(2)),
    };
  });

  const total_grid = hours.reduce((s, h) => s + h.grid_kwh, 0);
  const total_cost = hours.reduce((s, h) => s + h.grid_kwh * h.tariff_bdt_per_kwh, 0);

  return {
    scenario_id: "demo-scenario-01",
    server: "SuryaGrid (preview)",
    directive_interpretation: [
      {
        note_index: 0,
        applies: true,
        directive_type: "solar_reduction",
        structured_adjustment: { hours: [10, 11, 12, 13, 14], factor: 0.5 },
        explanation: "reduce solar to 50% between 10am and 2pm",
      },
      {
        note_index: 1,
        applies: true,
        directive_type: "no_discharge_window",
        structured_adjustment: { hours: [0, 1, 2, 3, 4, 5] },
        explanation: "do not discharge overnight until 5am",
      },
    ],
    hourly_plan: hours,
    summary: {
      total_grid_kwh: Number(total_grid.toFixed(2)),
      total_cost_bdt: Number(total_cost.toFixed(2)),
      peak_grid_kwh: Number(Math.max(...hours.map((h) => h.grid_kwh)).toFixed(2)),
      solar_used_total: Number(hours.reduce((s, h) => s + h.solar_used_kwh, 0).toFixed(2)),
      solar_curtailed_total: 0,
      battery_charged_total: 0,
      battery_discharged_total: Number(hours.reduce((s, h) => s + h.battery_discharge_kwh, 0).toFixed(2)),
      initial_battery_kwh: 50,
      final_battery_kwh: 54.6,
      neutrality_delta_kwh: -4.6,
    },
  };
}
