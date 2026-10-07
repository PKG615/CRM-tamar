import { useEffect, useState } from "react";
import { api, getToken } from "../api/client";
import { useAuth } from "../context/AuthContext";

const STAGES = ["NEW", "CONTACTED", "REPLIED", "INTERESTED", "MEETING", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

function formatMoney(n) {
  if (!n) return "—";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}

export default function Deals() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const { canWrite } = useAuth();

  function load() {
    api.get("/deals").then(setItems).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function updateStage(dealId, stage) {
    setItems((prev) => prev.map((d) => (d.id === dealId ? { ...d, stage } : d)));
    try {
      await api.put(`/deals/${dealId}`, { stage });
    } catch (e) {
      setError(e.message);
      load();
    }
  }

  async function downloadCsv() {
    const res = await fetch("/api/deals/export.csv", { headers: { Authorization: `Bearer ${getToken()}` } });
    if (!res.ok) { setError("Could not export CSV"); return; }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "deals.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Deals</h2>
        <button className="btn secondary" onClick={downloadCsv}>Export CSV</button>
      </div>
      {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}
      {items.length === 0 && !error ? (
        <p className="empty-state">No deals yet — create one from a lead's detail page.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Deal</th><th>Amount</th><th>Probability</th><th>Stage</th><th>Expected close</th></tr>
          </thead>
          <tbody>
            {items.map((d) => (
              <tr key={d.id}>
                <td style={{ fontWeight: 500 }}>{d.name}</td>
                <td style={{ fontFamily: "var(--font-mono)" }}>{formatMoney(d.amount)}</td>
                <td>{d.probability}%</td>
                <td>
                  <select value={d.stage} disabled={!canWrite} onChange={(e) => updateStage(d.id, e.target.value)}>
                    {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td>{d.expected_close_date || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
