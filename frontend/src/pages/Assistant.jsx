import { useState, useRef, useEffect } from "react";
import { api } from "../api/client";

const SUGGESTIONS = [
  "Which leads have the highest score right now?",
  "Who hasn't been followed up with in a while?",
  "Summarize my pipeline by stage",
];

export default function Assistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function ask(question) {
    if (!question.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const res = await api.post("/ai/assistant", { question });
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 140px)" }}>
      <div className="panel-header"><h2>AI Sales Assistant</h2></div>

      <div style={{ flex: 1, overflowY: "auto", padding: 18 }}>
        {messages.length === 0 && (
          <div>
            <p style={{ color: "var(--text-muted)", fontSize: 13.5, marginBottom: 14 }}>
              Ask about your leads, pipeline, or follow-ups — answers are grounded in your actual CRM data.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
              {SUGGESTIONS.map((s) => (
                <button key={s} className="btn secondary" onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 14, display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "75%",
              background: m.role === "user" ? "var(--ink)" : "#EDEFEA",
              color: m.role === "user" ? "#fff" : "var(--text)",
              padding: "10px 14px",
              borderRadius: 4,
              fontSize: 13.5,
              whiteSpace: "pre-wrap",
            }}>
              {m.text}
            </div>
          </div>
        ))}
        {busy && <p style={{ color: "var(--text-muted)", fontSize: 12.5 }}>Thinking…</p>}
        {error && <p className="error-text">{error}</p>}
        <div ref={endRef} />
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, padding: 16, borderTop: "1px solid var(--border)" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your leads or pipeline…"
          style={{ flex: 1 }}
        />
        <button className="btn" type="submit" disabled={busy}>Send</button>
      </form>
    </div>
  );
}
