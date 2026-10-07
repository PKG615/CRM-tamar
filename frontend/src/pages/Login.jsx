import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";
import { api } from "../api/client";

export default function Login() {
  const [mode, setMode] = useState("login"); // login | register | forgot
  const [slug, setSlug] = useState(import.meta.env.DEV ? "demo-agency" : "");
  const [email, setEmail] = useState(import.meta.env.DEV ? "admin@demo.com" : "");
  const [password, setPassword] = useState(import.meta.env.DEV ? "admin123" : "");
  const [orgName, setOrgName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  const { login, register } = useAuth();
  const { t, lang, setLang, languages } = useLanguage();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(slug, email, password);
        navigate("/");
      } else if (mode === "register") {
        await register(orgName, adminName, email, password);
        navigate("/");
      } else if (mode === "forgot") {
        await api.post("/auth/forgot-password", { organization_slug: slug, email });
        setForgotSent(true);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function switchMode(next) {
    setMode(next);
    setError("");
    setForgotSent(false);
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 6, marginBottom: 10 }}>
          {languages.map((l) => (
            <button
              key={l.code}
              type="button"
              onClick={() => setLang(l.code)}
              style={{
                background: lang === l.code ? "var(--ink)" : "transparent",
                border: "1px solid var(--border-strong)",
                borderRadius: 3,
                color: lang === l.code ? "#fff" : "var(--text-muted)",
                fontSize: 11.5,
                padding: "3px 9px",
                cursor: "pointer",
              }}
            >
              {l.label}
            </button>
          ))}
        </div>

        <h1>{t("login.title")}</h1>
        <p>
          {mode === "login" && t("login.sign_in_subtitle")}
          {mode === "register" && t("login.register_subtitle")}
          {mode === "forgot" && t("login.forgot_subtitle")}
        </p>

        {mode === "forgot" && forgotSent ? (
          <p style={{ color: "var(--accent)", fontSize: 13.5 }}>{t("login.reset_sent")}</p>
        ) : (
          <form onSubmit={handleSubmit}>
            {mode === "register" && (
              <>
                <div className="field">
                  <label>{t("login.company_name")}</label>
                  <input value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
                </div>
                <div className="field">
                  <label>{t("login.your_name")}</label>
                  <input value={adminName} onChange={(e) => setAdminName(e.target.value)} required />
                </div>
              </>
            )}
            {(mode === "login" || mode === "forgot") && (
              <div className="field">
                <label>{t("login.workspace")}</label>
                <input value={slug} onChange={(e) => setSlug(e.target.value)} required />
              </div>
            )}
            <div className="field">
              <label>{t("login.email")}</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            {mode !== "forgot" && (
              <div className="field">
                <label>{t("login.password")}</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
            )}

            {error && <div className="error-text">{error}</div>}

            <button className="btn" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center", marginTop: "6px" }}>
              {loading ? "…" : mode === "login" ? t("login.sign_in") : mode === "register" ? t("login.create_workspace") : t("login.send_reset_link")}
            </button>
          </form>
        )}

        <p style={{ marginTop: 18, fontSize: 12.5, display: "flex", flexDirection: "column", gap: 6 }}>
          {mode === "login" && (
            <>
              <span><a href="#" onClick={(e) => { e.preventDefault(); switchMode("forgot"); }}>{t("login.forgot_password")}</a></span>
              <span>{t("login.new_here")} <a href="#" onClick={(e) => { e.preventDefault(); switchMode("register"); }}>{t("login.create_a_workspace")}</a></span>
            </>
          )}
          {mode === "register" && (
            <span>{t("login.already_set_up")} <a href="#" onClick={(e) => { e.preventDefault(); switchMode("login"); }}>{t("login.sign_in")}</a></span>
          )}
          {mode === "forgot" && (
            <span><a href="#" onClick={(e) => { e.preventDefault(); switchMode("login"); }}>{t("login.back_to_sign_in")}</a></span>
          )}
        </p>
      </div>
    </div>
  );
}
