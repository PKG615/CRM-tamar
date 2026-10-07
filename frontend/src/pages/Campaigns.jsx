import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const STATUSES = ["NEW", "CONTACTED", "REPLIED", "INTERESTED", "MEETING", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

function NewCampaign({ onCreated }) {
  const [name, setName] = useState("");
  const [channel, setChannel] = useState("EMAIL");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [statusIn, setStatusIn] = useState([]);
  const [city, setCity] = useState("");
  const [minScore, setMinScore] = useState("");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function buildFilters() {
    const filters = {};
    if (statusIn.length) filters.status_in = statusIn;
    if (city) filters.city = city;
    if (minScore) filters.min_score = Number(minScore);
    return filters;
  }

  async function runPreview() {
    setError("");
    try {
      const res = await api.post("/campaigns/preview", { name: name || "x", channel, message: message || "x", filters: buildFilters() });
      setPreview(res.count);
    } catch (e) {
      setError(e.message);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.post("/campaigns", { name, channel, subject: channel === "EMAIL" ? subject : undefined, message, filters: buildFilters() });
      setName(""); setSubject(""); setMessage(""); setStatusIn([]); setCity(""); setMinScore(""); setPreview(null);
      onCreated();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleStatus(s) {
    setStatusIn((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
    setPreview(null);
  }

  return (
    <form onSubmit={submit} style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        <input placeholder="Campaign name" value={name} onChange={(e) => setName(e.target.value)} required style={{ flex: 1 }} />
        <select value={channel} onChange={(e) => { setChannel(e.target.value); setPreview(null); }}>
          <option value="EMAIL">Email</option>
          <option value="SMS">SMS</option>
        </select>
      </div>

      {channel === "EMAIL" && (
        <input placeholder="Subject line" value={subject} onChange={(e) => setSubject(e.target.value)} required
               style={{ width: "100%", marginBottom: 10 }} />
      )}

      <textarea
        placeholder="Message — use {{business_name}}, {{city}}, {{category}} as placeholders"
        value={message}
        onChange={(e) => { setMessage(e.target.value); setPreview(null); }}
        required
        rows={4}
        style={{ width: "100%", marginBottom: 10, fontFamily: "var(--font-body)", padding: 8, border: "1px solid var(--border-strong)", borderRadius: 3 }}
      />

      <div style={{ marginBottom: 10 }}>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 6px" }}>Audience filters (optional)</p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
          {STATUSES.map((s) => (
            <button type="button" key={s} onClick={() => toggleStatus(s)}
                    className={statusIn.includes(s) ? "btn" : "btn secondary"} style={{ padding: "4px 10px", fontSize: 11.5 }}>
              {s}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input placeholder="City" value={city} onChange={(e) => { setCity(e.target.value); setPreview(null); }} style={{ flex: 1 }} />
          <input type="number" placeholder="Min lead score" value={minScore} onChange={(e) => { setMinScore(e.target.value); setPreview(null); }} style={{ flex: 1 }} />
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button type="button" className="btn secondary" onClick={runPreview}>Preview audience</button>
        {preview !== null && <span style={{ fontSize: 13, color: "var(--text-muted)" }}>Will reach <strong>{preview}</strong> leads</span>}
        <span style={{ flex: 1 }} />
        <button className="btn" type="submit" disabled={busy}>{busy ? "Queuing…" : "Send campaign"}</button>
      </div>
      {error && <div className="error-text" style={{ marginTop: 8 }}>{error}</div>}
    </form>
  );
}

function StatusTag({ status }) {
  const tone = status === "COMPLETED" ? "won" : status === "FAILED" || status === "CANCELLED" ? "lost" : "";
  return <span className={`tag ${tone}`}>{status}</span>;
}

export default function Campaigns() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const { canWrite } = useAuth();

  function load() {
    api.get("/campaigns").then(setItems).catch((e) => setError(e.message));
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000); // campaigns run in the background; poll for progress
    return () => clearInterval(interval);
  }, []);

  async function cancel(id) {
    await api.post(`/campaigns/${id}/cancel`, {});
    load();
  }

  return (
    <>
      {canWrite && <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-header"><h2>New campaign</h2></div>
        <NewCampaign onCreated={load} />
      </div>}

      <div className="panel">
        <div className="panel-header"><h2>Campaigns</h2></div>
        {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}
        {items.length === 0 && !error ? (
          <p className="empty-state">No campaigns sent yet.</p>
        ) : (
          <table>
            <thead><tr><th>Name</th><th>Channel</th><th>Progress</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 500 }}>{c.name}</td>
                  <td>{c.channel}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
                    {c.sent + c.failed}/{c.total} {c.failed > 0 && <span style={{ color: "var(--warn)" }}>({c.failed} failed)</span>}
                  </td>
                  <td><StatusTag status={c.status} /></td>
                  <td>
                    {canWrite && ["QUEUED", "RUNNING"].includes(c.status) && (
                      <button className="btn secondary" onClick={() => cancel(c.id)}>Cancel</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
