import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, Boxes, CalendarClock, Replace, Database, FileText, Layers, MessageSquareText, Server } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Card, ErrorNote, PageHeader, Skeleton, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, timeAgo, titleCase } from "../lib/format";

function Stat({ icon, label, value, loading }: { icon: React.ReactNode; label: string; value: React.ReactNode; loading?: boolean }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between text-muted"><span className="text-sm">{label}</span>{icon}</div>
      {loading ? <Skeleton className="mt-3 h-8 w-20" /> : <p className="mt-2 text-3xl font-bold tracking-tight">{value}</p>}
    </Card>
  );
}

export default function Dashboard() {
  const docs = useQuery({ queryKey: ["documents", "overview"], queryFn: () => api.documents({ limit: 100 }) });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs(8), refetchInterval: 5000 });
  const ready = useQuery({ queryKey: ["ready"], queryFn: api.readiness, refetchInterval: 15000 });

  const items = docs.data?.items ?? [];
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = items.filter((d) => d.effective_date && d.effective_date >= today && d.status === "ACTIVE").sort((a, b) => a.effective_date!.localeCompare(b.effective_date!)).slice(0, 4);
  const replaced = items.filter((d) => d.status === "SUPERSEDED").sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 4);
  const chunks = items.reduce((n, d) => n + d.chunk_count, 0);
  const superseded = items.filter((d) => d.status === "SUPERSEDED").length;
  const byType = Object.entries(items.reduce<Record<string, number>>((acc, d) => ({ ...acc, [d.document_type]: (acc[d.document_type] ?? 0) + 1 }), {})).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...byType.map(([, n]) => n));

  return (
    <>
      <PageHeader title="Overview" subtitle="What's in your library and how the system is doing."
        actions={<Link to="/ask" className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:brightness-110"><MessageSquareText className="size-4" />Ask a question</Link>} />

      {docs.error ? <ErrorNote error={docs.error} /> : null}
      {!docs.isLoading && (docs.data?.total ?? 0) === 0 && (
        <Card className="mb-6 overflow-hidden">
          <div className="bg-gradient-to-r from-brand/15 to-cyan-500/10 p-6">
            <h2 className="text-lg font-bold">Welcome to GovLens. Let's add your first documents.</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted">GovLens answers questions only from documents you give it, so start by adding a few official PDFs.</p>
            <ol className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
              {[["1", "Find official PDFs", "Browse trusted government sources.", "/resources", "Find documents"], ["2", "Add them", "Upload files or paste a PDF link.", "/documents", "Go to Documents"], ["3", "Ask questions", "Get cited, checked answers.", "/ask", "Ask a question"]].map(([n, t, d, to, cta]) => (
                <li key={n} className="rounded-xl border border-line bg-surface p-4"><span className="mb-2 grid size-7 place-items-center rounded-full bg-brand-soft text-sm font-bold text-brand">{n}</span><p className="font-semibold">{t}</p><p className="mt-1 text-xs text-muted">{d}</p><Link to={to} className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-brand">{cta} <ArrowRight className="size-3.5" /></Link></li>
              ))}
            </ol>
          </div>
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={<FileText className="size-5" />} label="Documents" value={docs.data?.total ?? 0} loading={docs.isLoading} />
        <Stat icon={<Layers className="size-5" />} label="Searchable chunks" value={chunks.toLocaleString()} loading={docs.isLoading} />
        <Stat icon={<Boxes className="size-5" />} label="Superseded" value={superseded} loading={docs.isLoading} />
        <Stat icon={<Activity className="size-5" />} label="Queued jobs" value={(jobs.data ?? []).filter((j) => j.status === "PENDING" || j.status === "RUNNING").length} loading={jobs.isLoading} />
      </div>

      {items.length > 0 && (
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <Card className="p-5"><h2 className="mb-3 flex items-center gap-2 font-semibold"><CalendarClock className="size-5 text-brand" />Taking effect soon</h2>
            {upcoming.length === 0 ? <p className="text-sm text-muted">Nothing in your library has a future effective date.</p> : <ul className="divide-y divide-line">{upcoming.map((d) => (
              <li key={d.id}><Link to={`/documents/${d.id}`} className="-mx-2 flex items-center justify-between gap-3 rounded-xl px-2 py-2.5 hover:bg-raised"><span className="min-w-0"><span className="block truncate font-medium">{d.document_number}</span><span className="block truncate text-xs text-muted">{d.title}</span></span><Badge tone="brand">{fmtDate(d.effective_date)}</Badge></Link></li>))}</ul>}</Card>
          <Card className="p-5"><h2 className="mb-3 flex items-center gap-2 font-semibold"><Replace className="size-5 text-warn" />Recently superseded</h2>
            {replaced.length === 0 ? <p className="text-sm text-muted">No document has been replaced yet.</p> : <ul className="divide-y divide-line">{replaced.map((d) => (
              <li key={d.id}><Link to={`/documents/${d.id}`} className="-mx-2 flex items-center justify-between gap-3 rounded-xl px-2 py-2.5 hover:bg-raised"><span className="min-w-0"><span className="block truncate font-medium">{d.document_number}</span><span className="block truncate text-xs text-muted">{d.title}</span></span><StatusBadge status={d.status} /></Link></li>))}</ul>}</Card>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Recent documents</h2><Link to="/documents" className="flex items-center gap-1 text-sm text-brand">View all <ArrowRight className="size-4" /></Link></div>
          {docs.isLoading ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}</div> : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted">No documents yet. Upload a PDF from the Documents page.</p>
          ) : (
            <ul className="divide-y divide-line">
              {[...items].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 6).map((d) => (
                <li key={d.id}><Link to={`/documents/${d.id}`} className="-mx-2 flex items-center justify-between gap-3 rounded-xl px-2 py-3 hover:bg-raised">
                  <div className="min-w-0"><p className="truncate font-medium">{d.title}</p><p className="text-xs text-muted">{d.document_number} · {titleCase(d.document_type)} · {fmtDate(d.issue_date)}</p></div>
                  <StatusBadge status={d.status} />
                </Link></li>
              ))}
            </ul>
          )}
        </Card>

        <div className="space-y-6">
          <Card className="p-5">
            <h2 className="mb-4 font-semibold">System health</h2>
            {ready.isLoading ? <Skeleton className="h-24" /> : (
              <ul className="space-y-3 text-sm">
                {Object.entries(ready.data?.checks ?? {}).map(([name, c]) => (
                  <li key={name} className="flex items-center justify-between" title={c.detail ?? undefined}>
                    <span className="flex items-center gap-2 capitalize text-muted">{name === "database" ? <Database className="size-4" /> : <Server className="size-4" />}{name}</span>
                    <Badge tone={c.ok ? "ok" : name === "reranker" ? "warn" : "bad"}>{c.ok ? "Operational" : "Unavailable"}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="p-5">
            <h2 className="mb-4 font-semibold">By document type</h2>
            {byType.length === 0 ? <p className="text-sm text-muted">Nothing to chart yet.</p> : (
              <ul className="space-y-3">
                {byType.map(([t, n]) => (
                  <li key={t} className="text-sm"><div className="mb-1 flex justify-between"><span>{titleCase(t)}</span><span className="text-muted">{n}</span></div>
                    <div className="h-2 rounded-full bg-raised"><div className="h-2 rounded-full bg-gradient-to-r from-brand to-cyan-500 transition-all" style={{ width: `${(n / max) * 100}%` }} /></div></li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <Card className="mt-6 p-5">
        <h2 className="mb-4 font-semibold">Recent ingestion</h2>
        {(jobs.data ?? []).length === 0 ? <p className="text-sm text-muted">No ingestion jobs yet.</p> : (
          <ul className="divide-y divide-line text-sm">
            {(jobs.data ?? []).map((j) => (
              <li key={j.id} className="flex items-center justify-between gap-3 py-2.5">
                <span className="truncate">{j.original_filename ?? j.file_path}</span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-muted">{timeAgo(j.created_at)}<StatusBadge status={j.status} /></span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
