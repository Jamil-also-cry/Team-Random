export default function BatteryForm({ battery, onChange }) {
  const update = (key, value) =>
    onChange({ ...battery, [key]: value === "" ? "" : Number(value) });

  return (
    <div className="card">
      <div className="card-header">
        <h3>Battery</h3>
        <span className="muted">full kWh view (matches optimizer API)</span>
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Capacity (kWh)</label>
          <input
            type="number"
            min="0"
            value={battery.capacity_kwh}
            onChange={(e) => update("capacity_kwh", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Initial energy (kWh)</label>
          <input
            type="number"
            min="0"
            value={battery.initial_energy_kwh}
            onChange={(e) => update("initial_energy_kwh", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Minimum energy (kWh)</label>
          <input
            type="number"
            min="0"
            value={battery.minimum_energy_kwh}
            onChange={(e) => update("minimum_energy_kwh", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Max charge (kWh/h)</label>
          <input
            type="number"
            min="0"
            value={battery.max_charge_kwh_per_hour}
            onChange={(e) => update("max_charge_kwh_per_hour", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Max discharge (kWh/h)</label>
          <input
            type="number"
            min="0"
            value={battery.max_discharge_kwh_per_hour}
            onChange={(e) => update("max_discharge_kwh_per_hour", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
