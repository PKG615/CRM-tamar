export default function StatusTag({ status }) {
  const cls = status === "WON" ? "won" : status === "LOST" ? "lost" : "";
  return <span className={`tag ${cls}`}>{status}</span>;
}
