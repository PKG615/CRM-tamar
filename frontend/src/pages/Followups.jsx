import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

function Section({ title, items, onComplete, tone }) {
  const { canWrite } = useAuth();
  return (
    <div className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-header"><h2>{title}</h2><span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{items.length}</span></div>
      {items.length === 0 ? (
        <p className="empty-state">Nothing here.</p>
      ) : (
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((f) => (
            <li key={f.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 18px", borderBottom: "1px solid var(--border)" }}>
              <div>
                <div style={{ fontWeight: 500 }}>{f.notes || "Follow-up"}</div>
                <div style={{ fontSize: 12, color: tone === "warn" ? "var(--warn)" : "var(--text-muted)" }}>
                  Due {f.due_date}{f.due_time ? ` at ${f.due_time}` : ""} · {f.priority}
                </div>
              </div>
              {canWrite && <button className="btn secondary" onClick={() => onComplete(f.id)}>Mark done</button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Followups() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  function load() {
    api.get("/followups").then(setData).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function complete(id) {
    await api.post(`/followups/${id}/complete`, {});
    load();
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p className="empty-state">Loading…</p>;

  return (
    <>
      <Section title="Overdue" items={data.overdue} onComplete={complete} tone="warn" />
      <Section title="Due today" items={data.due_today} onComplete={complete} />
      <Section title="Upcoming" items={data.upcoming} onComplete={complete} />
    </>
  );
}
