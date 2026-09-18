const HOURS = Array.from({ length: 24 }, (_, i) => i);

export default function ProfilesTable({ hours, onChange }) {
  const update = (idx, key, value) => {
    const parsed = value === "" ? 0 : Number(value);
    const safe = Number.isFinite(parsed) ? parsed : 0;
    const next = hours.map((h, i) =>
      i === idx ? { ...h, [key]: safe } : h
    );
    onChange(next);
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3>24-Hour Profiles</h3>
        <span className="muted">demand &middot; solar &middot; tariff (BDT/kWh)</span>
      </div>
      <div className="profiles-scroll">
        <table className="profiles-table">
          <thead>
            <tr>
              <th>Hr</th>
              <th>Demand (kWh)</th>
              <th>Solar (kWh)</th>
              <th>Tariff (BDT/kWh)</th>
            </tr>
          </thead>
          <tbody>
            {HOURS.map((h) => (
              <tr key={h}>
                <th scope="row">{String(h).padStart(2, "0")}:00</th>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={hours[h].demand_kwh}
                    onChange={(e) => update(h, "demand_kwh", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={hours[h].solar_kwh}
                    onChange={(e) => update(h, "solar_kwh", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.1"
                    value={hours[h].tariff_bdt_per_kwh}
                    onChange={(e) => update(h, "tariff_bdt_per_kwh", e.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
