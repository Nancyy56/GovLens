import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Clock, MessageSquareText, ThumbsUp, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorNote, PageHeader, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import type { Analytics as A } from "../lib/types";

const pct = (n: number | null) => (n === null ? "—" : `${Math.round(n * 100)}%`);

function Tile({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint?: string }) {
  return <Card className="p-5"><div className="flex items-center justify-between text-muted"><span className="text-sm">{label}</span>{icon}</div><p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>{hint && <p className="mt-1 text-xs text-muted">{hint}</p>}</Card>;
}

/** Hand-rolled SVG area chart: no charting dependency, scales with its container. */
function QueriesChart({ data }: { data: A["per_day"] }) {
  const W = 640, H = 180, P = { l: 28, r: 8, t: 10, b: 22 };
  const max = Math.max(1, ...data.map((d) => d.queries));
  const x = (i: number) => P.l + (data.length <= 1 ? 0 : (i / (data.length - 1)) * (W - P.l - P.r));
  const y = (v: number) => H - P.b - (v / max) * (H - P.t - P.b);
  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.queries).toFixed(1)}`).join(" ");
  const area = `${line} L${x(data.length - 1)},${H - P.b} L${x(0)},${H - P.b} Z`;
  const ticks = [0, Math.ceil(max / 2), max];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Questions per day">
      <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="var(--brand)" stopOpacity="0.35" /><stop offset="1" stopColor="var(--brand)" stopOpacity="0" /></linearGradient></defs>
      {ticks.map((t) => <g key={t}><line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke="var(--line)" /><text x={P.l - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill="var(--muted)">{t}</text></g>)}
      <path d={area} fill="url(#area)" /><path d={line} fill="none" stroke="var(--brand)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {data.map((d, i) => <g key={d.day}><circle cx={x(i)} cy={y(d.queries)} r="3.5" fill="var(--brand)"><title>{d.day}: {d.queries} question(s)</title></circle>
        {(i === 0 || i === data.length - 1 || i % Math.ceil(data.length / 6) === 0) && <text x={x(i)} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">{d.day.slice(5)}</text>}</g>)}
    </svg>
  );
}

export default function Analytics() {
  const [days, setDays] = useState(14);
  const q = useQuery({ queryKey: ["analytics", days], queryFn: () => api.analytics(days) });
  const d = q.data;
  const topMax = Math.max(1, ...(d?.top_documents ?? []).map((t) => t.citations));

  return (
    <>
      <PageHeader title="Analytics" subtitle="How the system is used and where answers fall short."
        actions={<div className="flex rounded-xl bg-raised p-1 text-sm">{[7, 14, 30, 90].map((n) => <button key={n} onClick={() => setDays(n)} className={`rounded-lg px-3 py-1.5 font-medium ${days === n ? "bg-surface shadow-sm" : "text-muted"}`}>{n}d</button>)}</div>} />
      {q.error ? <ErrorNote error={q.error} /> : null}
      {q.isLoading || !d ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div> : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile icon={<MessageSquareText className="size-5" />} label="Questions" value={d.total_queries.toLocaleString()} hint={`${d.unique_users} user${d.unique_users === 1 ? "" : "s"}`} />
            <Tile icon={<BadgeCheck className="size-5" />} label="Answered with sources" value={pct(d.total_queries ? d.answered_rate : null)} hint={`Verified statements: ${pct(d.verified_rate)}`} />
            <Tile icon={<ThumbsUp className="size-5" />} label="Satisfaction" value={pct(d.satisfaction)} hint={`${d.helpful} 👍 · ${d.not_helpful} 👎 of ${d.rated} rated`} />
            <Tile icon={<Clock className="size-5" />} label="Response time" value={`${(d.avg_latency_ms / 1000).toFixed(1)}s`} hint={`p95 ${(d.p95_latency_ms / 1000).toFixed(1)}s`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="p-5 lg:col-span-2"><h2 className="mb-3 font-semibold">Questions per day</h2>{d.total_queries === 0 ? <p className="py-10 text-center text-sm text-muted">No questions in this period yet.</p> : <QueriesChart data={d.per_day} />}</Card>
            <Card className="p-5"><h2 className="mb-4 font-semibold">Most cited documents</h2>
              {d.top_documents.length === 0 ? <p className="text-sm text-muted">Nothing cited yet.</p> : <ul className="space-y-3">{d.top_documents.map((t) => (
                <li key={t.document_number} className="text-sm"><div className="mb-1 flex justify-between"><span className="font-medium">{t.document_number}</span><span className="text-muted">{t.citations}</span></div>
                  <div className="h-2 rounded-full bg-raised"><div className="h-2 rounded-full bg-gradient-to-r from-brand to-cyan-500" style={{ width: `${(t.citations / topMax) * 100}%` }} /></div></li>))}</ul>}</Card>
          </div>

          <Card className="p-5">
            <h2 className="mb-1 flex items-center gap-2 font-semibold"><AlertTriangle className="size-5 text-warn" />Worth a look</h2>
            <p className="mb-4 text-sm text-muted">Questions rated not helpful, answered without sources, or containing statements the sources didn't support. Usually a sign a document is missing.</p>
            {d.flagged.length === 0 ? <p className="text-sm text-muted">Nothing flagged. 🎉</p> : (
              <ul className="divide-y divide-line text-sm">{d.flagged.map((f) => (
                <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 py-3"><div className="min-w-0"><p className="font-medium">{f.question}</p><p className="text-xs text-muted">{f.username} · {timeAgo(f.created_at)}</p></div>
                  <div className="flex items-center gap-2"><Badge tone={f.reason === "Rated not helpful" ? "bad" : "warn"}>{f.reason}</Badge>
                    <Link to={`/ask?q=${encodeURIComponent(f.question)}`} className="text-xs font-medium text-brand">Re-ask</Link></div></li>))}</ul>)}
          </Card>
          <p className="flex items-center gap-2 text-xs text-muted"><Users className="size-3.5" />Visible to administrators only. Question text is stored to power history and these insights.</p>
        </div>
      )}
    </>
  );
}
