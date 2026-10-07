import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import ScoreBar from "../components/ScoreBar";
import StatusTag from "../components/StatusTag";
import { useAuth } from "../context/AuthContext";

function timeAgo(iso) {
  const d = new Date(iso);
  return d.toLocaleString();
}

export default function LeadDetail() {
  const { id } = useParams();
  const [lead, setLead] = useState(null);
  const [activities, setActivities] = useState([]);
  const [pitches, setPitches] = useState([]);
  const [deals, setDeals] = useState([]);
  const [audits, setAudits] = useState([]);
  const [dealName, setDealName] = useState("");
  const [dealAmount, setDealAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [auditBusy, setAuditBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [team, setTeam] = useState([]);
  const { canWrite, canManage } = useAuth();

  const load = useCallback(() => {
    api.get(`/leads/${id}`).then(setLead).catch((e) => setError(e.message));
    api.get(`/leads/${id}/activities`).then(setActivities).catch(() => {});
    api.get(`/leads/${id}/pitches`).then(setPitches).catch(() => {});
    api.get("/deals", { lead_id: id }).then(setDeals).catch(() => {});
    api.get(`/leads/${id}/audits`).then(setAudits).catch(() => {});
    api.get("/users/directory").then(setTeam).catch(() => {});
  }, [id]);

  useEffect(load, [load]);

  async function createDeal(e) {
    e.preventDefault();
    if (!dealName.trim()) return;
    try {
      await api.post("/deals", { lead_id: id, name: dealName.trim(), amount: dealAmount ? Number(dealAmount) : undefined });
      setDealName("");
      setDealAmount("");
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function assign(userId) {
    if (!userId) return;
    setError("");
    try {
      await api.put(`/leads/${id}/assign`, { assigned_to: userId });
      setNotice("Lead reassigned.");
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function convertToCustomer() {
    try {
      await api.post("/customers/convert", { lead_id: id });
      setNotice("Converted to customer.");
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function generatePitch() {
    setBusy(true);
    setError("");
    try {
      await api.post(`/leads/${id}/pitch`);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendPitch(pitchId) {
    await api.post(`/leads/${id}/pitch/${pitchId}/send`);
    load();
  }

  async function recalculateScore() {
    setBusy(true);
    try {
      await api.post("/ai/lead-score", { lead_id: id });
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function runAudit() {
    setAuditBusy(true);
    setError("");
    try {
      await api.post(`/leads/${id}/audit`);
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setAuditBusy(false);
    }
  }

  if (!lead) return <div className="empty-state">{error || "Loading…"}</div>;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <h1>{lead.business_name}</h1>
          <p style={{ color: "var(--text-muted)", margin: "4px 0 0" }}>
            {lead.category || "—"} · {lead.city || "—"} · {lead.phone || "no phone"}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {canManage ? (
            <select value={lead.assigned_to || ""} onChange={(e) => assign(e.target.value)} title="Assign owner">
              <option value="">Unassigned</option>
              {team.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          ) : (
            <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
              Owner: {team.find((t) => t.id === lead.assigned_to)?.name || "Unassigned"}
            </span>
          )}
          <StatusTag status={lead.status} />
        </div>
      </div>

      {notice && <p style={{ color: "var(--accent)", fontSize: 13 }}>{notice}</p>}
      {error && <p className="error-text">{error}</p>}

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 20 }}>
        <div className="panel">
          <div className="panel-header">
            <h2>AI Pitch</h2>
            {canWrite && (
              <button className="btn secondary" onClick={generatePitch} disabled={busy}>
                {busy ? "Generating…" : "Generate pitch"}
              </button>
            )}
          </div>
          <div style={{ padding: 16 }}>
            {pitches.length === 0 ? (
              <p className="empty-state">No pitch generated yet.</p>
            ) : (
              (() => {
                const hasPriorContact = pitches.some((p) =>
                  ["SENT", "DELIVERED", "READ", "REPLIED"].includes(p.status)
                );
                return pitches.map((p) => (
                  <div key={p.id} style={{ border: "1px solid var(--border)", borderRadius: 3, padding: 12, marginBottom: 10 }}>
                    <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{p.message}</p>
                    {p.status === "DRAFT" && !hasPriorContact && (
                      <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--text-muted)" }}>
                        First message to this lead — sent as a pre-approved WhatsApp template, not this exact text
                        (Meta requires a template for first contact; configure WHATSAPP_TEMPLATE_NAME).
                      </p>
                    )}
                    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10 }}>
                      <span className="tag">{p.status}</span>
                      {canWrite && p.status === "DRAFT" && (
                        <button className="btn" onClick={() => sendPitch(p.id)}>Send via WhatsApp</button>
                      )}
                    </div>
                  </div>
                ));
              })()
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Lead score</h2>
            {canWrite && <button className="btn secondary" onClick={recalculateScore} disabled={busy}>Recalculate</button>}
          </div>
          <div style={{ padding: 16 }}>
            <ScoreBar score={lead.lead_score} />
            <p style={{ color: "var(--text-muted)", fontSize: 12.5, marginTop: 10 }}>
              Opportunity: <strong>{lead.opportunity_level || "—"}</strong>
              {lead.estimated_deal_value_min && (
                <> · Est. value ₹{lead.estimated_deal_value_min}–₹{lead.estimated_deal_value_max}</>
              )}
            </p>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header">
          <h2>Website audit</h2>
          {canWrite && (
            <button className="btn secondary" onClick={runAudit} disabled={auditBusy || !lead.website}>
              {auditBusy ? "Auditing…" : "Run audit"}
            </button>
          )}
        </div>
        <div style={{ padding: 16 }}>
          {!lead.website ? (
            <p className="empty-state">This lead has no website to audit.</p>
          ) : audits.length === 0 ? (
            <p className="empty-state">No audit run yet.</p>
          ) : (
            (() => {
              const latest = audits[0];
              return (
                <>
                  <div style={{ display: "flex", gap: 24, marginBottom: 14 }}>
                    {[
                      ["Overall", latest.overall_score],
                      ["SEO", latest.seo_score],
                      ["Mobile", latest.mobile_score],
                      ["Performance", latest.performance_score],
                      ["Security", latest.security_score],
                      ["Content", latest.content_score],
                    ].map(([label, val]) => (
                      <div key={label}>
                        <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{label}</div>
                        <div style={{ fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 600, color: "var(--ink)" }}>
                          {val ?? "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                  {latest.recommendations && latest.recommendations.length > 0 && (
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "var(--text-muted)" }}>
                      {latest.recommendations.map((r, i) => <li key={i} style={{ marginBottom: 4 }}>{r}</li>)}
                    </ul>
                  )}
                </>
              );
            })()
          )}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header">
          <h2>Deals</h2>
          {canWrite && <button className="btn secondary" onClick={convertToCustomer}>Convert to customer</button>}
        </div>
        <div style={{ padding: 16 }}>
          {canWrite && <form onSubmit={createDeal} style={{ display: "flex", gap: 8, marginBottom: 14 }}>
            <input placeholder="Deal name" value={dealName} onChange={(e) => setDealName(e.target.value)} style={{ flex: 2 }} />
            <input type="number" placeholder="Amount (₹)" value={dealAmount} onChange={(e) => setDealAmount(e.target.value)} style={{ flex: 1 }} />
            <button className="btn" type="submit">Add deal</button>
          </form>}
          {deals.length === 0 ? (
            <p className="empty-state">No deals for this lead yet.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {deals.map((d) => (
                <li key={d.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                  <span>{d.name}</span>
                  <span className="tag">{d.stage}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="panel" style={{ marginTop: 20 }}>
        <div className="panel-header"><h2>Activity timeline</h2></div>
        <div style={{ padding: 16 }}>
          {activities.length === 0 ? (
            <p className="empty-state">No activity yet.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {activities.map((a) => (
                <li key={a.id} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)", fontSize: 13 }}>
                  <strong>{a.type.replace(/_/g, " ")}</strong>
                  {a.description ? ` — ${a.description}` : ""}
                  <span style={{ float: "right", color: "var(--text-muted)", fontSize: 12 }}>{timeAgo(a.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}
