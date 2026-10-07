import { useEffect, useState } from "react";
import { api, getToken } from "../api/client";
import { useAuth } from "../context/AuthContext";

function formatMoney(n) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n || 0);
}

function NewProposalForm({ deals, onCreated }) {
  const [dealId, setDealId] = useState("");
  const [items, setItems] = useState([{ service: "", quantity: 1, unit_price: 0, discount: 0, tax_percent: 18 }]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function updateItem(idx, field, value) {
    setItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  }

  function addItem() {
    setItems((prev) => [...prev, { service: "", quantity: 1, unit_price: 0, discount: 0, tax_percent: 18 }]);
  }

  async function submit(e) {
    e.preventDefault();
    const deal = deals.find((d) => d.id === dealId);
    if (!deal) { setError("Pick a deal first"); return; }
    setBusy(true);
    setError("");
    try {
      await api.post("/proposals", {
        deal_id: dealId,
        lead_id: deal.lead_id,
        line_items: items.map((it) => ({
          service: it.service,
          quantity: Number(it.quantity),
          unit_price: Number(it.unit_price),
          discount: Number(it.discount),
          tax_percent: Number(it.tax_percent),
        })),
        validity_days: 30,
      });
      setItems([{ service: "", quantity: 1, unit_price: 0, discount: 0, tax_percent: 18 }]);
      setDealId("");
      onCreated();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
      <div className="field">
        <label>Deal</label>
        <select value={dealId} onChange={(e) => setDealId(e.target.value)} required>
          <option value="">Select a deal…</option>
          {deals.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      </div>

      {items.map((item, idx) => (
        <div key={idx} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input placeholder="Service" value={item.service} onChange={(e) => updateItem(idx, "service", e.target.value)} style={{ flex: 2 }} required />
          <input type="number" placeholder="Qty" value={item.quantity} onChange={(e) => updateItem(idx, "quantity", e.target.value)} style={{ flex: 1 }} min="1" />
          <input type="number" placeholder="Unit price" value={item.unit_price} onChange={(e) => updateItem(idx, "unit_price", e.target.value)} style={{ flex: 1 }} min="0" />
          <input type="number" placeholder="Tax %" value={item.tax_percent} onChange={(e) => updateItem(idx, "tax_percent", e.target.value)} style={{ flex: 1 }} min="0" />
        </div>
      ))}
      <button type="button" className="btn secondary" onClick={addItem} style={{ marginBottom: 12 }}>+ Add line item</button>

      {error && <div className="error-text">{error}</div>}
      <div>
        <button className="btn" type="submit" disabled={busy}>{busy ? "Creating…" : "Create proposal"}</button>
      </div>
    </form>
  );
}

export default function Proposals() {
  const [items, setItems] = useState([]);
  const [deals, setDeals] = useState([]);
  const [error, setError] = useState("");
  const { canWrite } = useAuth();

  function load() {
    api.get("/proposals").then(setItems).catch((e) => setError(e.message));
    api.get("/deals").then(setDeals).catch(() => {});
  }

  useEffect(load, []);

  async function send(id) {
    await api.post(`/proposals/${id}/send`, {});
    load();
  }

  async function downloadPdf(proposalId, proposalNumber) {
    const res = await fetch(`/api/proposals/${proposalId}/pdf`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) {
      setError("Could not generate the PDF");
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${proposalNumber}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  return (
    <div className="panel">
      <div className="panel-header"><h2>Proposals</h2></div>
      {canWrite && <NewProposalForm deals={deals} onCreated={load} />}
      {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}
      {items.length === 0 && !error ? (
        <p className="empty-state">No proposals yet.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Number</th><th>Subtotal</th><th>Grand total</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id}>
                <td style={{ fontFamily: "var(--font-mono)" }}>{p.proposal_number}</td>
                <td>{formatMoney(p.subtotal)}</td>
                <td style={{ fontWeight: 500 }}>{formatMoney(p.grand_total)}</td>
                <td><span className="tag">{p.status}</span></td>
                <td style={{ display: "flex", gap: 8 }}>
                  {canWrite && p.status === "DRAFT" && <button className="btn secondary" onClick={() => send(p.id)}>Send</button>}
                  <button className="btn secondary" onClick={() => downloadPdf(p.id, p.proposal_number)}>Download PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
