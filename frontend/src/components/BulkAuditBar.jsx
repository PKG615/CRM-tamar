import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const ACTIVE = ["QUEUED", "RUNNING"];

/**
 * "Audit unaudited leads" button + live progress. The audits run in the background
 * worker (python -m app.worker), so this just enqueues and polls; it survives page
 * reloads because progress lives in the DB, not in the browser.
 */
export default function BulkAuditBar({ onFinished }) {
  const { canWrite } = useAuth();
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const wasActive = useRef(false);

  // Pick up a job that's already running (e.g. after a page reload).
  useEffect(() => {
    api.get("/jobs").then((jobs) => {
      const latest = jobs.find((j) => j.type === "BULK_AUDIT");
      if (latest && ACTIVE.includes(latest.status)) setJob(latest);
    }).catch(() => {});
  }, []);

  const active = job && ACTIVE.includes(job.status);

  useEffect(() => {
    if (active) wasActive.current = true;
    if (!active) {
      if (wasActive.current) { wasActive.current = false; onFinished?.(); }
      return undefined;
    }
    const t = setInterval(() => {
      api.get(`/jobs/${job.id}`).then(setJob).catch(() => {});
    }, 2000);
    return () => clearInterval(t);
  }, [active, job?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function start() {
    setBusy(true);
    setError("");
    try {
      setJob(await api.post("/leads/bulk-audit", { only_unaudited: true }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    try { setJob(await api.post(`/jobs/${job.id}/cancel`, {})); } catch (e) { setError(e.message); }
  }

  if (!canWrite) return null;

  const pct = job && job.total ? Math.round((job.processed / job.total) * 100) : 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
      <button className="btn secondary" onClick={start} disabled={busy || active}>
        {active ? "Auditing…" : "Audit unaudited leads"}
      </button>

      {active && (
        <>
          <div style={{ width: 180, height: 6, background: "var(--border)", borderRadius: 2 }}>
            <div style={{ width: `${pct}%`, height: 6, background: "var(--accent)", borderRadius: 2, transition: "width .3s" }} />
          </div>
          <span style={{ fontSize: 12.5, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            {job.status === "QUEUED" ? "Queued — waiting for the worker" : `${job.processed}/${job.total}`}
          </span>
          <button className="btn secondary" onClick={cancel} style={{ padding: "4px 10px", fontSize: 12 }}>Cancel</button>
        </>
      )}

      {job && !active && (
        <span style={{ fontSize: 12.5, color: job.status === "FAILED" ? "var(--danger)" : "var(--text-muted)" }}>
          Last run {job.status.toLowerCase()}: {job.succeeded} audited{job.failed ? `, ${job.failed} failed` : ""}
          {job.error ? ` — ${job.error}` : ""}
        </span>
      )}
      {error && <span className="error-text" style={{ margin: 0 }}>{error}</span>}
    </div>
  );
}
