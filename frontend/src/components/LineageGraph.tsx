import { useNavigate } from "react-router-dom";
import type { DocumentDetail, RelatedDocument } from "../lib/types";

const COL = { SUPERSEDES: "var(--warn)", AMENDS: "var(--brand)", REFERENCES: "var(--muted)" } as const;
const W = 720, NODE_W = 190, NODE_H = 46, GAP = 14;

function Node({ x, y, label, sub, current, onClick }: { x: number; y: number; label: string; sub?: string; current?: boolean; onClick?: () => void }) {
  return (
    <g transform={`translate(${x},${y})`} onClick={onClick} className={onClick ? "cursor-pointer" : ""} role={onClick ? "link" : undefined} tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => { if (onClick && (e.key === "Enter" || e.key === " ")) onClick(); }}>
      <rect width={NODE_W} height={NODE_H} rx="12" fill={current ? "var(--brand)" : "var(--surface)"} stroke={current ? "var(--brand)" : "var(--line)"} strokeWidth="1.5" />
      <text x={NODE_W / 2} y={NODE_H / 2 - (sub ? 3 : -4)} textAnchor="middle" fontSize="13" fontWeight="600" fill={current ? "#fff" : "var(--ink)"}>{label}</text>
      {sub && <text x={NODE_W / 2} y={NODE_H / 2 + 12} textAnchor="middle" fontSize="10" fill={current ? "#ffffffcc" : "var(--muted)"}>{sub}</text>}
    </g>
  );
}

/** Left: documents that act on this one. Centre: this document. Right: documents this one acts on. */
export default function LineageGraph({ doc }: { doc: DocumentDetail }) {
  const nav = useNavigate();
  const left = doc.incoming, right = doc.outgoing;
  const rows = Math.max(left.length, right.length, 1);
  const H = rows * (NODE_H + GAP) + GAP;
  const cy = H / 2 - NODE_H / 2;
  const xL = 0, xC = (W - NODE_W) / 2, xR = W - NODE_W;
  const yAt = (i: number, n: number) => GAP + i * (NODE_H + GAP) + ((rows - n) * (NODE_H + GAP)) / 2;

  const edge = (r: RelatedDocument, i: number, n: number, side: "L" | "R") => {
    const y = yAt(i, n) + NODE_H / 2;
    const [x1, x2] = side === "L" ? [xL + NODE_W, xC] : [xC + NODE_W, xR];
    const mx = (x1 + x2) / 2;
    return (
      <g key={r.relationship_id}>
        <path d={`M${x1},${side === "L" ? y : cy + NODE_H / 2} C${mx},${side === "L" ? y : cy + NODE_H / 2} ${mx},${side === "L" ? cy + NODE_H / 2 : y} ${x2},${side === "L" ? cy + NODE_H / 2 : y}`}
          fill="none" stroke={COL[r.relationship_type]} strokeWidth="2" markerEnd={`url(#arrow-${r.relationship_type})`} strokeDasharray={r.relationship_type === "REFERENCES" ? "5 4" : undefined} />
        <text x={mx} y={(y + cy + NODE_H / 2) / 2 - 6} textAnchor="middle" fontSize="10" fontWeight="600" fill={COL[r.relationship_type]}>{r.relationship_type.toLowerCase()}</text>
      </g>
    );
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="group" aria-label="Document lineage graph">
      <defs>{(Object.keys(COL) as (keyof typeof COL)[]).map((k) => (
        <marker key={k} id={`arrow-${k}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill={COL[k]} /></marker>))}</defs>
      {left.map((r, i) => edge(r, i, left.length, "L"))}
      {right.map((r, i) => edge(r, i, right.length, "R"))}
      {left.map((r, i) => <Node key={r.relationship_id} x={xL} y={yAt(i, left.length)} label={r.document_number} sub={r.status === "SUPERSEDED" ? "superseded" : r.document_type.toLowerCase()} onClick={() => nav(`/documents/${r.document_id}`)} />)}
      <Node x={xC} y={cy} label={doc.document_number} sub="this document" current />
      {right.map((r, i) => <Node key={r.relationship_id} x={xR} y={yAt(i, right.length)} label={r.document_number} sub={r.status === "SUPERSEDED" ? "superseded" : r.document_type.toLowerCase()} onClick={() => nav(`/documents/${r.document_id}`)} />)}
    </svg>
  );
}
