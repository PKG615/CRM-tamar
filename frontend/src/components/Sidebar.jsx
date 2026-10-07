import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../context/LanguageContext";

const LINKS = [
  { to: "/", key: "nav.dashboard", end: true },
  { to: "/leads", key: "nav.leads" },
  { to: "/pipeline", key: "nav.pipeline" },
  { to: "/deals", key: "nav.deals" },
  { to: "/proposals", key: "nav.proposals" },
  { to: "/followups", key: "nav.followups" },
  { to: "/customers", key: "nav.customers" },
  { to: "/reports", key: "nav.reports" },
  { to: "/campaigns", key: "nav.campaigns", needs: "canWrite" },
  { to: "/assistant", key: "nav.assistant" },
  { to: "/team", key: "nav.team", needs: "canManage" },
  { to: "/settings", key: "nav.settings", needs: "canManage" },
];

export default function Sidebar() {
  const auth = useAuth();
  const { logout, me } = auth;
  const { t, lang, setLang, languages } = useLanguage();
  const links = LINKS.filter((l) => !l.needs || auth[l.needs]);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        Ledger<span>CRM</span>
      </div>
      <nav className="sidebar-nav">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            {t(link.key)}
          </NavLink>
        ))}
      </nav>
      <div style={{ marginTop: "auto", padding: "0 24px" }}>
        {me && (
          <div style={{ fontSize: 12, color: "#B7BEC9", paddingBottom: 8, lineHeight: 1.4 }}>
            {me.name}
            <div style={{ color: "#8A93A3" }}>{me.role.replace("_", " ").toLowerCase()}</div>
          </div>
        )}
        <div style={{ display: "flex", gap: 6, paddingBottom: 10 }}>
          {languages.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              title={t("common.language")}
              style={{
                background: lang === l.code ? "rgba(255,255,255,0.12)" : "transparent",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: 3,
                color: lang === l.code ? "#fff" : "#B7BEC9",
                fontSize: 11.5,
                padding: "3px 9px",
                cursor: "pointer",
              }}
            >
              {l.label}
            </button>
          ))}
        </div>
        <button
          className="sidebar-link"
          style={{ background: "none", border: "none", width: "100%", textAlign: "left", padding: "10px 0" }}
          onClick={logout}
        >
          {t("nav.logout")}
        </button>
      </div>
    </aside>
  );
}
