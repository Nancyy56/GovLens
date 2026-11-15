import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScrollText } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import { Badge, Button, Card, ErrorNote, Skeleton, inputCls } from "./ui";

const PAGE = 20;
const TONE = (a: string) => (a.includes("failed") || a.endsWith("delete") ? "bad" : a.startsWith("auth") ? "neutral" : a.startsWith("user") ? "warn" : "brand") as "bad" | "neutral" | "warn" | "brand";

export default function AuditLog() {
  const [action, setAction] = useState("");
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(0);
  useEffect(() => { const t = setTimeout(() => { setTerm(search); setPage(0); }, 300); return () => clearTimeout(t); }, [search]);
  const log = useQuery({ queryKey: ["audit", action, term, page], queryFn: () => api.audit({ limit: PAGE, offset: page * PAGE, action, search: term }), placeholderData: keepPreviousData });
  const total = log.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
        <h2 className="flex items-center gap-2 font-semibold"><ScrollText className="size-5 text-brand" />Audit log <span className="text-sm font-normal text-muted">({total})</span></h2>
        <div className="flex flex-wrap gap-2">
          <input className={`${inputCls} w-48 py-2`} placeholder="Search user or target" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search audit log" />
          <select className={`${inputCls} w-auto py-2`} value={action} onChange={(e) => { setAction(e.target.value); setPage(0); }} aria-label="Action"><option value="">All actions</option>{(log.data?.actions ?? []).map((a) => <option key={a} value={a}>{a}</option>)}</select>
        </div>
      </div>
      {log.error ? <div className="p-4"><ErrorNote error={log.error} /></div> : log.isLoading ? <div className="p-4"><Skeleton className="h-40" /></div> : (log.data?.items ?? []).length === 0 ? <p className="p-8 text-center text-sm text-muted">No entries match.</p> : (
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">When</th><th className="px-4 py-3">Who</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Target</th><th className="hidden px-4 py-3 lg:table-cell">Details</th></tr></thead>
          <tbody className="divide-y divide-line">{log.data!.items.map((e) => (
            <tr key={e.id}><td className="whitespace-nowrap px-4 py-2.5 text-muted">{fmtDateTime(e.created_at)}</td><td className="px-4 py-2.5 font-medium">{e.username}{e.ip && <span className="ml-2 text-xs font-normal text-muted">{e.ip}</span>}</td>
              <td className="px-4 py-2.5"><Badge tone={TONE(e.action)}>{e.action}</Badge></td><td className="max-w-48 truncate px-4 py-2.5" title={e.target ?? ""}>{e.target ?? "—"}</td><td className="hidden max-w-64 truncate px-4 py-2.5 text-muted lg:table-cell" title={e.detail ?? ""}>{e.detail ?? ""}</td></tr>))}</tbody></table></div>
      )}
      {pages > 1 && <div className="flex items-center justify-between border-t border-line p-3 text-sm text-muted"><span>Page {page + 1} of {pages}</span>
        <div className="flex gap-2"><Button variant="ghost" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}><ChevronLeft className="size-4" />Prev</Button><Button variant="ghost" size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next<ChevronRight className="size-4" /></Button></div></div>}
    </Card>
  );
}
