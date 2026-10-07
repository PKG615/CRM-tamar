import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const ROLES = [
  ["ADMIN", "Admin", "Everything, including managing users"],
  ["SALES_MANAGER", "Sales manager", "Settings, assignment, bulk actions"],
  ["SALES_EXECUTIVE", "Sales executive", "Works leads, deals, proposals"],
  ["VIEWER", "Viewer", "Read-only"],
];
const roleLabel = (r) => ROLES.find(([v]) => v === r)?.[1] || r;

function AddMember({ onCreated }) {
  const [form, setForm] = useState({ name: "", email: "", role: "SALES_EXECUTIVE", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const payload = { name: form.name, email: form.email, role: form.role };
      if (form.password) payload.password = form.password;
      const res = await api.post("/users", payload);
      setForm({ name: "", email: "", role: "SALES_EXECUTIVE", password: "" });
      setResult(res);
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} style={{ padding: 16, borderBottom: "1px solid var(--border)" }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input placeholder="Full name" value={form.name} onChange={set("name")} required style={{ flex: 1, minWidth: 150 }} />
        <input type="email" placeholder="Email" value={form.email} onChange={set("email")} required style={{ flex: 1.3, minWidth: 180 }} />
        <select value={form.role} onChange={set("role")}>
          {ROLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
        </select>
        <input type="text" placeholder="Initial password (optional — leave blank to email an invite)" value={form.password} onChange={set("password")}
               minLength={8} maxLength={72} style={{ flex: 1.6, minWidth: 240 }} />
        <button className="btn" type="submit" disabled={busy}>{busy ? "Adding…" : "Add member"}</button>
      </div>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "8px 0 0" }}>
        Leave the password blank to email them a "set your password" link (if email is configured for this workspace).
        Set one directly if you'd rather share it yourself.
      </p>
      {error && <div className="error-text">{error}</div>}
      {result && (
        <p style={{ fontSize: 12.5, margin: "8px 0 0", color: "var(--accent)" }}>
          {result.invited_by_email
            ? `Invite email sent to ${result.email}.`
            : result.temporary_password
              ? <>Added <strong>{result.email}</strong> — no email sent, share this temporary password directly: <code>{result.temporary_password}</code></>
              : `Added ${result.email}.`}
        </p>
      )}
    </form>
  );
}

export default function Team() {
  const { me, isAdmin } = useAuth();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function load() {
    api.get("/users").then(setUsers).catch((e) => setError(e.message));
  }
  useEffect(load, []);

  async function update(user, patch) {
    setError("");
    setNotice("");
    try {
      await api.put(`/users/${user.id}`, patch);
      load();
    } catch (e) {
      setError(e.message);
      load();
    }
  }

  async function resetPassword(user) {
    const pw = window.prompt(`New password for ${user.name} (8–72 characters):`);
    if (!pw) return;
    setError("");
    try {
      await api.post(`/users/${user.id}/reset-password`, { new_password: pw });
      setNotice(`Password reset for ${user.name}. Share it with them directly.`);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Team</h2>
        <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>{users.length} members</span>
      </div>
      {isAdmin && <AddMember onCreated={load} />}
      {!isAdmin && (
        <p style={{ padding: "12px 16px", margin: 0, fontSize: 12.5, color: "var(--text-muted)", borderBottom: "1px solid var(--border)" }}>
          Only admins can add or change team members.
        </p>
      )}
      {error && <p className="error-text" style={{ padding: "12px 16px", margin: 0 }}>{error}</p>}
      {notice && <p style={{ padding: "12px 16px", margin: 0, color: "var(--accent)", fontSize: 13 }}>{notice}</p>}

      <table>
        <thead>
          <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th>{isAdmin && <th></th>}</tr>
        </thead>
        <tbody>
          {users.map((u) => {
            const self = u.id === me?.id;
            return (
              <tr key={u.id} style={{ cursor: "default", opacity: u.is_active ? 1 : 0.55 }}>
                <td style={{ fontWeight: 500 }}>{u.name}{self && <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> (you)</span>}</td>
                <td>{u.email}</td>
                <td>
                  {isAdmin && !self ? (
                    <select value={u.role} onChange={(e) => update(u, { role: e.target.value })}>
                      {ROLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                    </select>
                  ) : roleLabel(u.role)}
                </td>
                <td><span className="tag">{u.is_active ? "Active" : "Deactivated"}</span></td>
                {isAdmin && (
                  <td style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button className="btn secondary" onClick={() => resetPassword(u)}>Reset password</button>
                    {!self && (
                      <button className="btn secondary" onClick={() => update(u, { is_active: !u.is_active })}>
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
