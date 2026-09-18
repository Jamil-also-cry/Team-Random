const TYPE_LABEL = {
  solar_reduction: "Solar reduction",
  no_charge_window: "No-charge window",
  no_discharge_window: "No-discharge window",
  minimum_battery_reserve: "Min battery reserve",
  max_grid_window: "Max-grid window",
  no_op: "Ignored",
};

export default function DirectiveList({ interpretations }) {
  if (!interpretations?.length) return null;
  return (
    <div className="card">
      <div className="card-header">
        <h3>Interpreted Directives</h3>
        <span className="muted">how SuryaGrid read the operator notes</span>
      </div>
      <ul className="directive-list">
        {interpretations.map((d, i) => (
          <li key={i} className={`directive ${d.applies ? "applies" : "ignored"}`}>
            <div className="directive-head">
              <span className={`pill ${d.applies ? "pill-ok" : "pill-muted"}`}>
                {d.applies ? "applied" : "ignored"}
              </span>
              <strong>{TYPE_LABEL[d.directive_type] || d.directive_type}</strong>
            </div>
            <p className="directive-note">“{d.explanation}”</p>
            {d.structured_adjustment && (
              <pre className="directive-json">
                {JSON.stringify(d.structured_adjustment, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
