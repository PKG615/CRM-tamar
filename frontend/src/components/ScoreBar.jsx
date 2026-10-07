export default function ScoreBar({ score }) {
  const val = score ?? 0;
  const cls = val >= 70 ? "" : val >= 40 ? "warn" : "low";
  return (
    <div className="score">
      <div className="score-track">
        <div className={`score-fill ${cls}`} style={{ width: `${val}%` }} />
      </div>
      <span className="score-num">{val}</span>
    </div>
  );
}
