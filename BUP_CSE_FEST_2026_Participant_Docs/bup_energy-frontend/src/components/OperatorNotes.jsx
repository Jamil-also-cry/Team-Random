export default function OperatorNotes({ notes, onChange }) {
  const updateNote = (i, value) => {
    const next = notes.slice();
    next[i] = value;
    onChange(next);
  };
  const addNote = () => onChange([...notes, ""]);
  const removeNote = (i) => onChange(notes.filter((_, idx) => idx !== i));

  return (
    <div className="card">
      <div className="card-header">
        <h3>Operator Notes</h3>
        <span className="muted">free-text · parsed by SuryaGrid</span>
      </div>
      {notes.map((note, i) => (
        <div key={i} className="note-row">
          <textarea
            rows={2}
            value={note}
            placeholder='e.g. "reduce solar to 50% between 10am and 2pm"'
            onChange={(e) => updateNote(i, e.target.value)}
          />
          {notes.length > 1 && (
            <button type="button" className="ghost" onClick={() => removeNote(i)} aria-label="Remove note">
              ✕
            </button>
          )}
        </div>
      ))}
      <button type="button" className="secondary" onClick={addNote}>
        + Add note
      </button>
    </div>
  );
}
