import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import ScoreBar from "../components/ScoreBar";
import { useAuth } from "../context/AuthContext";

export default function Pipeline() {
  const [board, setBoard] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { canWrite } = useAuth();

  function load() {
    api.get("/pipeline").then(setBoard).catch((e) => setError(e.message));
  }

  useEffect(load, []);

  async function moveCard(leadId, newStatus) {
    // optimistic update
    setBoard((prev) => {
      if (!prev) return prev;
      const next = { ...prev, columns: { ...prev.columns } };
      let card = null;
      for (const stage of Object.keys(next.columns)) {
        const idx = next.columns[stage].findIndex((c) => c.id === leadId);
        if (idx >= 0) {
          card = next.columns[stage][idx];
          next.columns[stage] = next.columns[stage].filter((c) => c.id !== leadId);
        }
      }
      if (card) next.columns[newStatus] = [...(next.columns[newStatus] || []), card];
      return next;
    });

    try {
      await api.put(`/pipeline/${leadId}`, { new_status: newStatus });
    } catch (e) {
      setError(e.message);
      load(); // revert on failure
    }
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!board) return <p className="empty-state">Loading…</p>;

  return (
    <div className="kanban">
      {board.stages.map((stage) => (
        <div
          key={stage.name}
          className="kanban-column"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            const leadId = e.dataTransfer.getData("text/plain");
            if (leadId) moveCard(leadId, stage.name);
          }}
        >
          <div className="kanban-column-header">
            <span>{stage.name}</span>
            <span>{(board.columns[stage.name] || []).length}</span>
          </div>
          <div className="kanban-cards">
            {(board.columns[stage.name] || []).map((card) => (
              <div
                key={card.id}
                className="kanban-card"
                draggable={canWrite}
                onDragStart={(e) => e.dataTransfer.setData("text/plain", card.id)}
                onClick={() => navigate(`/leads/${card.id}`)}
              >
                <div className="kanban-card-name">{card.business_name}</div>
                <ScoreBar score={card.lead_score} />
                <div className="kanban-card-meta">
                  <span>{card.next_followup_date || "no follow-up"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
