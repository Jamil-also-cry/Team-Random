// Mirror of optimizer/optimizer.py defaults so the frontend sends a payload
// the Django view will happily consume.

export const HORIZON = 24;
export const DEFAULT_GRID_PRICE = 12.0;
export const DEFAULT_CAPACITY = 100.0;
export const DEFAULT_INITIAL_SOC = 50.0;
export const DEFAULT_MAX_POWER = 25.0;

export const EMPTY_PROFILE = Array.from({ length: HORIZON }, () => 0);

export function makeBlankScenario() {
  return {
    scenario_id: "demo-scenario-01",
    hours: EMPTY_PROFILE.map(() => ({
      demand_kwh: 0,
      solar_kwh: 0,
      tariff_bdt_per_kwh: DEFAULT_GRID_PRICE,
    })),
    battery: {
      capacity_kwh: DEFAULT_CAPACITY,
      initial_energy_kwh: DEFAULT_CAPACITY / 2,
      minimum_energy_kwh: 0,
      max_charge_kwh_per_hour: DEFAULT_MAX_POWER,
      max_discharge_kwh_per_hour: DEFAULT_MAX_POWER,
    },
    operator_notes: [""],
  };
}
