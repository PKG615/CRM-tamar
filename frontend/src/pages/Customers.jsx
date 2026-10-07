import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function Customers() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/customers").then(setItems).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="panel">
      <div className="panel-header"><h2>Customers</h2></div>
      {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}
      {items.length === 0 && !error ? (
        <p className="empty-state">No leads converted to customers yet.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Company</th><th>Contact</th><th>Phone</th><th>Email</th></tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 500 }}>{c.company_name}</td>
                <td>{c.contact_person || "—"}</td>
                <td>{c.phone || "—"}</td>
                <td>{c.email || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
