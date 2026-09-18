const COLUMNS = [
  { key: "hour", label: "Hr" },
  { key: "demand_kwh", label: "Demand" },
  { key: "solar_kwh", label: "Solar" },
  { key: "solar_used_kwh", label: "Solar used" },
  { key: "grid_kwh", label: "Grid" },
  { key: "battery_action", label: "Battery" },
  { key: "battery_kwh", label: "kWh moved" },
  { key: "battery_energy_after_kwh", label: "SoC after" },
  { key: "tariff_bdt_per_kwh", label: "Tariff" },
];

export default function HourlyPlanTable({ plan }) {
  return (
    <div className="card">
      <div className="card-header">
        <h3>Hourly Plan</h3>
        <span className="muted">24 rows · {plan.length} returned</span>
      </div>
      <div className="plan-scroll">
        <table className="plan-table">
          <thead>
            <tr>{COLUMNS.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {plan.map((row) => (
              <tr key={row.hour} className={row.battery_action !== "idle" ? "row-active" : ""}>
                {COLUMNS.map((c) => (
                  <td key={c.key} className={c.key === "battery_action" ? `action action-${row.battery_action}` : ""}>
                    {row[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
