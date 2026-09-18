import { useRef, useState } from "react";
import { postOptimize } from "../api/optimize.js";

/**
 * Drop a JSON request body — file picker OR drag-and-drop OR pasted text —
 * and POST it straight to /optimize-energy. Skips the form builder.
 */
export default function JsonSubmit({ onResult, onError, onLoading, busy }) {
  const inputRef = useRef(null);
  const [pasted, setPasted] = useState("");
  const [filename, setFilename] = useState("");
  const [parseError, setParseError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = async (file) => {
    if (!file) return;
    setFilename(file.name);
    try {
      const text = await file.text();
      setPasted(text);
      setParseError(null);
    } catch {
      setParseError("Could not read the file.");
    }
  };

  const onPickFile = (e) => {
    const file = e.target.files?.[0];
    handleFile(file);
    e.target.value = "";
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const submit = async () => {
    setParseError(null);
    onError?.(null);
    let payload;
    try {
      payload = JSON.parse(pasted);
    } catch (err) {
      const msg = `Invalid JSON: ${err.message}. Hint: remove any trailing text, comments, or unclosed brackets before submitting.`;
      setParseError(msg);
      onError?.(msg);
      return;
    }

    // Strip wrapper shapes before hitting the API. The endpoint accepts a
    // single OptimizeRequest at the top level, so we unwrap:
    //   {cases:[{input:{...}},...]}  -> first case's input
    //   {inputs:[{...},...]}         -> first request
    //   [{...},...]                  -> first request
    //   {id, label, input:{...}}     -> single case wrapper -> its input
    let batch = null;
    let single = payload;
    if (payload && typeof payload === "object" && !Array.isArray(payload)) {
      if (Array.isArray(payload.cases)) {
        batch = payload.cases;
        single = payload.cases[0]?.input ?? null;
      } else if (Array.isArray(payload.inputs)) {
        batch = payload.inputs;
        single = batch[0] ?? null;
      } else if (
        payload.input &&
        typeof payload.input === "object" &&
        !Array.isArray(payload.input)
      ) {
        single = payload.input;
      }
    } else if (Array.isArray(payload)) {
      batch = payload;
      single = payload[0];
    }

    if (!single || typeof single !== "object") {
      const msg =
        "Could not find an OptimizeRequest in the JSON. Expected a single {scenario_id,...} request, a {cases:[{input:...},...]} wrapper, a {...} case with an input field, or a [...] array.";
      setParseError(msg);
      onError?.(msg);
      return;
    }

    onLoading?.(true);
    try {
      const data = await postOptimize(single);
      onResult?.(data);
      if (batch && batch.length > 1) {
        setParseError(
          `Submitted the first of ${batch.length} cases. To run all of them, use submit_cases.py on the backend.`
        );
      }
    } catch (err) {
      const msg = err.message || "Unknown error";
      setParseError(`Submit failed: ${msg}`);
      onError?.(msg);
    } finally {
      onLoading?.(false);
    }
  };

  const clear = () => {
    setPasted("");
    setFilename("");
    setParseError(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3>Submit JSON Directly</h3>
        <span className="muted">POST /optimize-energy</span>
      </div>

      <div
        className={`json-drop${dragOver ? " is-drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/json,.json"
          onChange={onPickFile}
          hidden
        />
        <span className="json-drop-title">
          {filename || "Drop a .json file here or click to choose"}
        </span>
        <span className="muted">
          Or paste the payload into the text area below.
        </span>
      </div>

      <textarea
        className="json-paste"
        rows={8}
        placeholder='{"scenario_id":"demo","hours":[...],"battery":{...},"operator_notes":["..."]}'
        value={pasted}
        onChange={(e) => setPasted(e.target.value)}
      />

      {parseError && (
        <div className="banner banner-error" role="alert">
          <strong>Parse failed.</strong>
          <span>{parseError}</span>
        </div>
      )}

      <div className="actions">
        <button
          className="primary"
          type="button"
          onClick={submit}
          disabled={busy || !pasted.trim()}
        >
          {busy ? "Submitting JSON…" : "Submit JSON"}
        </button>
        <button
          className="secondary"
          type="button"
          onClick={clear}
          disabled={busy || !pasted}
        >
          Clear
        </button>
      </div>
    </div>
  );
}
