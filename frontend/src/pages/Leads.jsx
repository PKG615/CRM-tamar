import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, getToken } from "../api/client";
import ScoreBar from "../components/ScoreBar";
import StatusTag from "../components/StatusTag";
import BulkAuditBar from "../components/BulkAuditBar";
import { useAuth } from "../context/AuthContext";

const STATUSES = ["NEW", "CONTACTED", "REPLIED", "INTERESTED", "MEETING", "PROPOSAL", "NEGOTIATION", "WON", "LOST"];

function DiscoverPanel({ onDiscovered }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const res = await api.post("/leads/discover", { query, city: city || undefined, max_results: 20 });
      setResult(res);
      onDiscovered();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn" onClick={() => setOpen(true)} style={{ marginBottom: 16 }}>
        Search leads on Google Maps
      </button>
    );
  }

  return (
    <div className="panel" style={{ marginBottom: 18 }}>
      <div className="panel-header">
        <h2>Search leads on Google Maps</h2>
        <button className="btn secondary" onClick={() => setOpen(false)}>Close</button>
      </div>
      <form onSubmit={submit} style={{ padding: 16, display: "flex", gap: 10 }}>
        <input placeholder="Business type — e.g. electronics store" value={query} onChange={(e) => setQuery(e.target.value)} style={{ flex: 2 }} required />
        <input placeholder="City — e.g. Gurugram" value={city} onChange={(e) => setCity(e.target.value)} style={{ flex: 1 }} />
        <button className="btn" type="submit" disabled={busy}>{busy ? "Searching…" : "Search"}</button>
      </form>
      {error && <p className="error-text" style={{ padding: "0 16px 16px" }}>{error}</p>}
      {result && (
        <p style={{ padding: "0 16px 16px", fontSize: 13, color: "var(--text-muted)" }}>
          Added {result.created_count} new lead{result.created_count === 1 ? "" : "s"}
          {result.skipped_duplicates > 0 ? ` (${result.skipped_duplicates} already existed)` : ""}.
        </p>
      )}
    </div>
  );
}

export default function Leads() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const navigate = useNavigate();
  const { canWrite } = useAuth();

  useEffect(() => {
    setLoading(true);
    api
      .get("/leads", { page, page_size: 20, search: search || undefined, status: status || undefined })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [page, search, status, refreshKey]);

  async function downloadCsv() {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    const res = await fetch(`/api/leads/export.csv?${params.toString()}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) { setError("Could not export CSV"); return; }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "leads.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  return (
    <>
      {canWrite && <DiscoverPanel onDiscovered={() => setRefreshKey((k) => k + 1)} />}
      <BulkAuditBar onFinished={() => setRefreshKey((k) => k + 1)} />

      <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        <input
          placeholder="Search business, phone, city…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          style={{ flex: 1, maxWidth: 320 }}
        />
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="panel">
        <div className="panel-header">
          <h2>Leads</h2>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{total} total</span>
            <button className="btn secondary" onClick={downloadCsv}>Export CSV</button>
          </div>
        </div>

        {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}

        {!loading && items.length === 0 && !error ? (
          <p className="empty-state">No leads match these filters yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Business</th>
                <th>Category</th>
                <th>City</th>
                <th>Score</th>
                <th>Status</th>
                <th>Next follow-up</th>
              </tr>
            </thead>
            <tbody>
              {items.map((lead) => (
                <tr key={lead.id} onClick={() => navigate(`/leads/${lead.id}`)}>
                  <td style={{ fontWeight: 500 }}>{lead.business_name}</td>
                  <td>{lead.category || "—"}</td>
                  <td>{lead.city || "—"}</td>
                  <td><ScoreBar score={lead.lead_score} /></td>
                  <td><StatusTag status={lead.status} /></td>
                  <td>{lead.next_followup_date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, padding: 14 }}>
          <button className="btn secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <button className="btn secondary" disabled={page * 20 >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      </div>
    </>
  );
}
