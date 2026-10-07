import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LanguageProvider, useLanguage } from "./context/LanguageContext";
import Sidebar from "./components/Sidebar";
import NotificationBell from "./components/NotificationBell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Leads from "./pages/Leads";
import LeadDetail from "./pages/LeadDetail";
import Pipeline from "./pages/Pipeline";
import Followups from "./pages/Followups";
import Customers from "./pages/Customers";
import Deals from "./pages/Deals";
import Proposals from "./pages/Proposals";
import Settings from "./pages/Settings";
import Reports from "./pages/Reports";
import Assistant from "./pages/Assistant";
import Team from "./pages/Team";
import SetPassword from "./pages/SetPassword";
import Campaigns from "./pages/Campaigns";

const TITLE_KEYS = {
  "/": "nav.dashboard",
  "/leads": "nav.leads",
  "/pipeline": "nav.pipeline",
  "/followups": "nav.followups",
  "/customers": "nav.customers",
  "/deals": "nav.deals",
  "/proposals": "nav.proposals",
  "/settings": "nav.settings",
  "/reports": "nav.reports",
  "/campaigns": "nav.campaigns",
  "/assistant": "nav.assistant",
  "/team": "nav.team",
};

function Protected({ children }) {
  const { isAuthed } = useAuth();
  const location = useLocation();
  if (!isAuthed) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

function Layout({ children }) {
  const location = useLocation();
  const { t } = useLanguage();
  const key = TITLE_KEYS[location.pathname];
  const title = key ? t(key) : (location.pathname.startsWith("/leads/") ? t("nav.leads") : "");
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">
        <div className="topbar">
          <h1>{title}</h1>
          <NotificationBell />
        </div>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <LanguageProvider>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/set-password" element={<SetPassword />} />
          <Route path="/" element={<Protected><Layout><Dashboard /></Layout></Protected>} />
          <Route path="/leads" element={<Protected><Layout><Leads /></Layout></Protected>} />
          <Route path="/leads/:id" element={<Protected><Layout><LeadDetail /></Layout></Protected>} />
          <Route path="/pipeline" element={<Protected><Layout><Pipeline /></Layout></Protected>} />
          <Route path="/followups" element={<Protected><Layout><Followups /></Layout></Protected>} />
          <Route path="/customers" element={<Protected><Layout><Customers /></Layout></Protected>} />
          <Route path="/deals" element={<Protected><Layout><Deals /></Layout></Protected>} />
          <Route path="/proposals" element={<Protected><Layout><Proposals /></Layout></Protected>} />
          <Route path="/settings" element={<Protected><Layout><Settings /></Layout></Protected>} />
          <Route path="/reports" element={<Protected><Layout><Reports /></Layout></Protected>} />
          <Route path="/campaigns" element={<Protected><Layout><Campaigns /></Layout></Protected>} />
          <Route path="/assistant" element={<Protected><Layout><Assistant /></Layout></Protected>} />
          <Route path="/team" element={<Protected><Layout><Team /></Layout></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </LanguageProvider>
  );
}
