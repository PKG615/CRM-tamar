import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, setToken } from "../api/client";

export default function SetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const mode = params.get("mode") || "reset";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const navigate = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.post("/auth/set-password", { token, new_password: password });
      setToken(res.access_token);
      setDone(true);
      setTimeout(() => navigate("/"), 800);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1>Invalid link</h1>
          <p>This link is missing its token. Please use the link from your email.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>{mode === "invite" ? "Welcome aboard" : "Reset your password"}</h1>
        <p>{mode === "invite" ? "Set a password to activate your account." : "Choose a new password below."}</p>

        {done ? (
          <p style={{ color: "var(--accent)", fontSize: 13.5 }}>Password set — signing you in…</p>
        ) : (
          <form onSubmit={submit}>
            <div className="field">
              <label>New password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
            </div>
            <div className="field">
              <label>Confirm password</label>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} minLength={8} required />
            </div>
            {error && <div className="error-text">{error}</div>}
            <button className="btn" type="submit" disabled={busy} style={{ width: "100%", justifyContent: "center", marginTop: 6 }}>
              {busy ? "Please wait…" : mode === "invite" ? "Activate account" : "Reset password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
