import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, Empty, ErrorNote, PageHeader, Skeleton, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate, titleCase } from "../lib/format";
import { DOCUMENT_TYPES } from "../lib/types";

export default function Timeline() {
  const docs = useQuery({ queryKey: ["documents", "timeline"], queryFn: () => api.documents({ limit: 500 }) });
  const [type, setType] = useState("");
  const [hideOld, setHideOld] = useState(false);

  const groups = useMemo(() => {
    const items = (docs.data?.items ?? []).filter((d) => (!type || d.document_type === type) && (!hideOld || d.status === "ACTIVE"));
    const dated = items.filter((d) => d.issue_date).sort((a, b) => b.issue_date!.localeCompare(a.issue_date!));
    const map = new Map<string, typeof dated>();
    for (const d of dated) {
      const key = new Date(d.issue_date!).toLocaleDateString(undefined, { month: "long", year: "numeric" });
      map.set(key, [...(map.get(key) ?? []), d]);
    }
    return { months: [...map.entries()], undated: items.filter((d) => !d.issue_date) };
  }, [docs.data, type, hideOld]);

  const empty = !docs.isLoading && groups.months.length === 0 && groups.undated.length === 0;

  return (
    <>
      <PageHeader title="Timeline" subtitle="Your documents in the order they were issued, with what is still in force."
        actions={<div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2 text-muted"><input type="checkbox" checked={hideOld} onChange={(e) => setHideOld(e.target.checked)} className="size-4 accent-[var(--brand)]" />In force only</label>
          <select className="rounded-xl border border-line bg-surface px-3 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)} aria-label="Type"><option value="">All types</option>{DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select>
        </div>} />

      {docs.error ? <ErrorNote error={docs.error} /> : null}
      {docs.isLoading ? <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div> : empty ? (
        <Card><Empty icon={<CalendarClock className="size-6" />} title="Nothing to show yet" hint="Documents appear here once they are uploaded and their issue date is read." /></Card>
      ) : (
        <div className="relative space-y-8 pl-6 before:absolute before:left-[7px] before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-line">
          {groups.months.map(([month, items]) => (
            <section key={month}>
              <h2 className="relative mb-3 text-sm font-semibold uppercase tracking-wide text-muted"><span className="absolute -left-6 top-1 size-3.5 rounded-full border-2 border-brand bg-bg" />{month}</h2>
              <div className="space-y-3">{items.map((d) => (
                <Link key={d.id} to={`/documents/${d.id}`} className="block"><Card className="rise p-4 transition hover:border-brand">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0"><p className="font-semibold">{d.document_number} <span className="font-normal text-muted">· {fmtDate(d.issue_date)}</span></p><p className="mt-0.5 truncate text-sm text-muted">{d.title}</p></div>
                    <div className="flex items-center gap-2"><Badge>{titleCase(d.document_type)}</Badge><StatusBadge status={d.status} /></div>
                  </div>
                  {d.effective_date && <p className="mt-2 text-xs text-muted">Takes effect {fmtDate(d.effective_date)}</p>}
                </Card></Link>))}</div>
            </section>
          ))}
          {groups.undated.length > 0 && (
            <section><h2 className="relative mb-3 text-sm font-semibold uppercase tracking-wide text-muted"><span className="absolute -left-6 top-1 size-3.5 rounded-full border-2 border-line bg-bg" />Date not found</h2>
              <div className="space-y-3">{groups.undated.map((d) => <Link key={d.id} to={`/documents/${d.id}`} className="block"><Card className="p-4 transition hover:border-brand"><p className="font-semibold">{d.document_number}</p><p className="text-sm text-muted">{d.title}</p></Card></Link>)}</div></section>
          )}
        </div>
      )}
    </>
  );
}
