import { useEffect, useState } from "react";
import { api } from "../api/client";

function formatMoney(n) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Reports() {
  const [dashboard, setDashboard] = useState(null);
  const [deals, setDeals] = useState([]);
  const [leads, setLeads] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/dashboard").then(setDashboard).catch((e) => setError(e.message));
    api.get("/deals").then(setDeals).catch(() => {});
    api.get("/leads", { page: 1, page_size: 100 }).then((r) => setLeads(r.items)).catch(() => {});
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!dashboard) return <p className="empty-state">Loading…</p>;

  const stageGroups = deals.reduce((acc, d) => {
    acc[d.stage] = acc[d.stage] || { count: 0, value: 0 };
    acc[d.stage].count += 1;
    acc[d.stage].value += Number(d.amount || 0);
    return acc;
  }, {});

  const topLeads = [...leads].sort((a, b) => b.lead_score - a.lead_score).slice(0, 10);

  return (
    <>
      <div className="stat-row">
        <div className="stat">
          <div className="stat-label">Win rate</div>
          <div className="stat-value accent">
            {dashboard.won_deals + dashboard.lost_deals > 0
              ? Math.round((dashboard.won_deals / (dashboard.won_deals + dashboard.lost_deals)) * 100)
              : 0}%
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Avg. deal size (won)</div>
          <div className="stat-value">
            {formatMoney(dashboard.won_deals > 0 ? dashboard.won_revenue / dashboard.won_deals : 0)}
          </div>
        </div>
        <div className="stat">
          <div className="stat-label">Total pipeline deals</div>
          <div className="stat-value">{deals.length}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div className="panel">
          <div className="panel-header"><h2>Deals by stage</h2></div>
          <div style={{ padding: 16 }}>
            {Object.keys(stageGroups).length === 0 ? (
              <p className="empty-state">No deals yet.</p>
            ) : (
              <table>
                <thead><tr><th>Stage</th><th>Count</th><th>Value</th></tr></thead>
                <tbody>
                  {Object.entries(stageGroups).map(([stage, g]) => (
                    <tr key={stage}>
                      <td>{stage}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{g.count}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{formatMoney(g.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><h2>Top 10 leads by score</h2></div>
          <div style={{ padding: 16 }}>
            {topLeads.length === 0 ? (
              <p className="empty-state">No leads yet.</p>
            ) : (
              <table>
                <thead><tr><th>Business</th><th>Score</th><th>Status</th></tr></thead>
                <tbody>
                  {topLeads.map((l) => (
                    <tr key={l.id}>
                      <td>{l.business_name}</td>
                      <td style={{ fontFamily: "var(--font-mono)" }}>{l.lead_score}</td>
                      <td>{l.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
