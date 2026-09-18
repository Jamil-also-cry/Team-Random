export default function ScenarioMeta({ scenarioId, onChange }) {
  return (
    <div className="field">
      <label htmlFor="scenario-id">Scenario ID</label>
      <input
        id="scenario-id"
        type="text"
        value={scenarioId}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. summer-peak-2026"
      />
    </div>
  );
}
