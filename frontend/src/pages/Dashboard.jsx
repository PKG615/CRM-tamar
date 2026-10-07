import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useLanguage } from "../context/LanguageContext";

function formatMoney(n) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n || 0);
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const { t } = useLanguage();

  useEffect(() => {
    api.get("/dashboard").then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="content"><p className="error-text">{error}</p></div>;
  if (!data) return <div className="content"><p className="empty-state">{t("common.loading")}</p></div>;

  return (
    <>
      <div className="stat-row">
        <div className="stat">
          <div className="stat-label">{t("dashboard.total_leads")}</div>
          <div className="stat-value">{data.total_leads}</div>
        </div>
        <div className="stat">
          <div className="stat-label">{t("dashboard.pipeline_value")}</div>
          <div className="stat-value">{formatMoney(data.pipeline_value)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">{t("dashboard.revenue_won")}</div>
          <div className="stat-value accent">{formatMoney(data.won_revenue)}</div>
        </div>
        <div className="stat">
          <div className="stat-label">{t("dashboard.overdue_followups")}</div>
          <div className={"stat-value" + (data.overdue_followups > 0 ? " warn" : "")}>{data.overdue_followups}</div>
        </div>
        <div className="stat">
          <div className="stat-label">{t("dashboard.won_lost")}</div>
          <div className="stat-value">{data.won_deals} / {data.lost_deals}</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><h2>{t("dashboard.funnel")}</h2></div>
        <div style={{ padding: "18px" }}>
          {Object.entries(data.lead_conversion_funnel).length === 0 ? (
            <p className="empty-state">{t("dashboard.no_leads")}</p>
          ) : (
            <table>
              <tbody>
                {Object.entries(data.lead_conversion_funnel).map(([status, count]) => (
                  <tr key={status}>
                    <td style={{ width: 160, fontWeight: 500 }}>{status}</td>
                    <td>
                      <div style={{ background: "var(--border)", height: 8, borderRadius: 2, width: "100%" }}>
                        <div
                          style={{
                            background: "var(--accent)",
                            height: 8,
                            borderRadius: 2,
                            width: `${Math.min(100, (count / data.total_leads) * 100)}%`,
                          }}
                        />
                      </div>
                    </td>
                    <td style={{ width: 50, fontFamily: "var(--font-mono)", textAlign: "right" }}>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
