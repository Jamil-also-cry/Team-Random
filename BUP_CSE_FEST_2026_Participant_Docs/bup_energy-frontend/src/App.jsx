import { useEffect, useMemo, useState } from "react";
import { makeBlankScenario } from "./api/contract.js";
import { postOptimize, checkHealth } from "./api/optimize.js";
import ScenarioMeta from "./components/ScenarioMeta.jsx";
import ProfilesTable from "./components/ProfilesTable.jsx";
import BatteryForm from "./components/BatteryForm.jsx";
import OperatorNotes from "./components/OperatorNotes.jsx";
import SummaryCards from "./components/SummaryCards.jsx";
import HourlyPlanTable from "./components/HourlyPlanTable.jsx";
import DirectiveList from "./components/DirectiveList.jsx";

function buildPayload({ scenarioId, hours, battery, notes }) {
  // Backend requires 1..3 non-blank operator notes (see api/serializers.py).
  // If the user cleared every note, fall back to a neutral baseline so the
  // request still validates instead of returning 400.
  const cleanedNotes = (notes || []).map((n) => n.trim()).filter(Boolean);
  const finalNotes = cleanedNotes.length
    ? cleanedNotes.slice(0, 3)
    : ["Run a baseline optimization with no special directives."];
  // Guarantee hour 0..23 ordering in case the table ever mutates it.
  const orderedHours = Array.from({ length: 24 }, (_, hour) => ({
    hour,
    ...(hours?.[hour] ?? {}),
  }));
  return {
    scenario_id: scenarioId.trim(),
    hours: orderedHours,
    battery,
    operator_notes: finalNotes,
  };
}

export default function App() {
  const initial = useMemo(makeBlankScenario, []);
  const [scenarioId, setScenarioId] = useState(initial.scenario_id);
  const [hours, setHours] = useState(initial.hours);
  const [battery, setBattery] = useState(initial.battery);
  const [notes, setNotes] = useState(initial.operator_notes);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");

  useEffect(() => {
    let cancelled = false;
    checkHealth().then((s) => {
      if (!cancelled) setBackendStatus(s.ok ? "online" : "offline");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = buildPayload({ scenarioId, hours, battery, notes });
      const data = await postOptimize(payload);
      setResult(data);
    } catch (err) {
      setError(err.message || "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    const fresh = makeBlankScenario();
    setScenarioId(fresh.scenario_id);
    setHours(fresh.hours);
    setBattery(fresh.battery);
    setNotes(fresh.operator_notes);
    setResult(null);
    setError(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>SuryaGrid · BUP Energy Optimizer</h1>
          <p className="muted">POSTs JSON to <code>/optimize-energy</code> via Vite proxy</p>
        </div>
        <div className="header-pills">
          <span className={`status-pill status-${backendStatus}`}>
            backend: {backendStatus}
          </span>
          {result && (
            <span className="server-pill">server: {result.server || "SuryaGrid"}</span>
          )}
        </div>
      </header>

      <main className="app-grid">
        <section className="form-column">
          <div className="card">
            <ScenarioMeta scenarioId={scenarioId} onChange={setScenarioId} />
          </div>
          <ProfilesTable hours={hours} onChange={setHours} />
          <BatteryForm battery={battery} onChange={setBattery} />
          <OperatorNotes notes={notes} onChange={setNotes} />

          <div className="actions">
            <button
              className="primary"
              type="button"
              onClick={handleRun}
              disabled={loading}
            >
              {loading ? "Running optimization…" : "Run optimization"}
            </button>
            <button className="secondary" type="button" onClick={handleReset} disabled={loading}>
              Reset
            </button>
          </div>

          {error && (
            <div className="banner banner-error" role="alert">
              <strong>Request failed.</strong>
              <span>{error}</span>
            </div>
          )}
        </section>

        <section className="result-column">
          {!result && !loading && !error && (
            <div className="card placeholder">
              <h3>No results yet</h3>
              <p className="muted">
                Fill the profiles and battery, add operator notes, then click
                <strong> Run optimization</strong>. Results will appear here.
              </p>
            </div>
          )}

          {result && (
            <>
              {result.plan_summary && (
                <div className="card plan-summary-card">
                  <div className="card-header">
                    <h3>Plan summary</h3>
                    <span className="muted">from Django optimizer</span>
                  </div>
                  <p>{result.plan_summary}</p>
                </div>
              )}
              <SummaryCards summary={result.summary} />
              <DirectiveList interpretations={result.directive_interpretation} />
              <HourlyPlanTable plan={result.hourly_plan} />
            </>
          )}
        </section>
      </main>
    </div>
  );
}
