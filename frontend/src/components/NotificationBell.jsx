import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  function load() {
    api.get("/notifications").then((res) => {
      setItems(res.items);
      setUnreadCount(res.unread_count);
    }).catch(() => {});
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000); // poll every 30s
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function markAllRead() {
    await api.post("/notifications/mark-all-read", {});
    load();
  }

  async function openNotification(n) {
    if (!n.is_read) {
      await api.post(`/notifications/${n.id}/read`, {});
    }
    setOpen(false);
    load();
    if (n.link) navigate(n.link);
  }

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        className="btn secondary"
        onClick={() => setOpen((o) => !o)}
        style={{ position: "relative" }}
      >
        Notifications
        {unreadCount > 0 && (
          <span style={{
            position: "absolute", top: -6, right: -6, background: "var(--warn)", color: "#fff",
            borderRadius: "50%", width: 18, height: 18, fontSize: 10.5, display: "flex",
            alignItems: "center", justifyContent: "center", fontFamily: "var(--font-mono)",
          }}>
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="panel" style={{
          position: "absolute", right: 0, top: "calc(100% + 6px)", width: 320, zIndex: 20,
          maxHeight: 400, overflowY: "auto", boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
        }}>
          <div className="panel-header">
            <h2 style={{ fontSize: 13 }}>Notifications</h2>
            {unreadCount > 0 && (
              <button className="btn secondary" style={{ padding: "4px 10px", fontSize: 11.5 }} onClick={markAllRead}>
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="empty-state" style={{ fontSize: 12.5 }}>No notifications yet.</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {items.map((n) => (
                <li
                  key={n.id}
                  onClick={() => openNotification(n)}
                  style={{
                    padding: "10px 16px", borderBottom: "1px solid var(--border)", cursor: "pointer",
                    background: n.is_read ? "transparent" : "var(--accent-soft)", fontSize: 12.5,
                  }}
                >
                  {n.message}
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
