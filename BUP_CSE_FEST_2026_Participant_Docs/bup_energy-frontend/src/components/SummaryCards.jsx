const CARDS = [
  { key: "total_grid_kwh", label: "Total grid (kWh)" },
  { key: "total_cost_bdt", label: "Total cost (BDT)" },
  { key: "peak_grid_kwh", label: "Peak grid (kWh)" },
  { key: "solar_used_total", label: "Solar used (kWh)" },
  { key: "solar_curtailed_total", label: "Solar curtailed (kWh)" },
  { key: "battery_charged_total", label: "Battery charged (kWh)" },
  { key: "battery_discharged_total", label: "Battery discharged (kWh)" },
  { key: "initial_battery_kwh", label: "Battery start (kWh)" },
  { key: "final_battery_kwh", label: "Battery end (kWh)" },
  { key: "neutrality_delta_kwh", label: "Neutrality Δ (kWh)" },
];

export default function SummaryCards({ summary }) {
  return (
    <div className="summary-grid">
      {CARDS.map((c) => (
        <div key={c.key} className="summary-card">
          <div className="summary-value">{summary?.[c.key] ?? "—"}</div>
          <div className="summary-label">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
