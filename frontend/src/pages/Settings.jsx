import { useEffect, useState } from "react";
import { api } from "../api/client";

function WeightsEditor({ weights, onChange }) {
  return (
    <div style={{ padding: 16 }}>
      {Object.entries(weights).map(([key, value]) => (
        <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
          <span style={{ fontSize: 13 }}>{key.replace(/_/g, " ")}</span>
          <input
            type="number"
            value={value}
            onChange={(e) => onChange({ ...weights, [key]: Number(e.target.value) })}
            style={{ width: 80, textAlign: "right" }}
          />
        </div>
      ))}
    </div>
  );
}

function RangesEditor({ ranges, onChange }) {
  return (
    <div style={{ padding: 16 }}>
      {Object.entries(ranges).map(([level, [lo, hi]]) => (
        <div key={level} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
          <span style={{ width: 70, fontSize: 13, fontWeight: 500 }}>{level}</span>
          <input type="number" value={lo} onChange={(e) => onChange({ ...ranges, [level]: [Number(e.target.value), hi] })} style={{ width: 100 }} />
          <span style={{ color: "var(--text-muted)" }}>to</span>
          <input type="number" value={hi} onChange={(e) => onChange({ ...ranges, [level]: [lo, Number(e.target.value)] })} style={{ width: 100 }} />
        </div>
      ))}
    </div>
  );
}

function StagesEditor({ stages, onCreate, onDelete }) {
  const [name, setName] = useState("");

  return (
    <div style={{ padding: 16 }}>
      <ul style={{ listStyle: "none", margin: "0 0 12px", padding: 0 }}>
        {stages.map((s) => (
          <li key={s.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <span>{s.order}. {s.name}</span>
            <button className="btn secondary" onClick={() => onDelete(s.id)}>Remove</button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: 8 }}>
        <input placeholder="New stage name" value={name} onChange={(e) => setName(e.target.value)} />
        <button
          className="btn secondary"
          onClick={() => { if (name.trim()) { onCreate(name.trim(), stages.length); setName(""); } }}
        >
          Add stage
        </button>
      </div>
    </div>
  );
}

export default function Settings() {
  const [weights, setWeights] = useState(null);
  const [ranges, setRanges] = useState(null);
  const [stages, setStages] = useState([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.get("/settings").then((s) => {
      setWeights(s.lead_scoring_weights);
      setRanges(s.opportunity_value_ranges);
    }).catch((e) => setError(e.message));
    api.get("/settings/pipeline-stages").then(setStages).catch(() => {});
  }

  useEffect(load, []);

  async function save() {
    setStatus("Saving…");
    try {
      await api.put("/settings", { lead_scoring_weights: weights, opportunity_value_ranges: ranges });
      setStatus("Saved");
      setTimeout(() => setStatus(""), 1500);
    } catch (e) {
      setError(e.message);
    }
  }

  async function addStage(name, order) {
    await api.post("/settings/pipeline-stages", { name, order });
    load();
  }

  async function removeStage(id) {
    await fetch(`/api/settings/pipeline-stages/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${localStorage.getItem("crm_token")}` },
    });
    load();
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!weights || !ranges) return <p className="empty-state">Loading…</p>;

  return (
    <>
      <p style={{ color: "var(--text-muted)", marginBottom: 18, fontSize: 13.5 }}>
        These control how leads are scored and valued across your whole workspace — nothing here is hard-coded in the app.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
        <div className="panel">
          <div className="panel-header"><h2>Lead scoring weights</h2></div>
          <WeightsEditor weights={weights} onChange={setWeights} />
        </div>
        <div className="panel">
          <div className="panel-header"><h2>Opportunity value ranges (₹)</h2></div>
          <RangesEditor ranges={ranges} onChange={setRanges} />
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <button className="btn" onClick={save}>Save changes</button>
        {status && <span style={{ marginLeft: 12, fontSize: 12.5, color: "var(--text-muted)" }}>{status}</span>}
      </div>

      <div className="panel">
        <div className="panel-header"><h2>Pipeline stages</h2></div>
        <StagesEditor stages={stages} onCreate={addStage} onDelete={removeStage} />
      </div>
    </>
  );
}
