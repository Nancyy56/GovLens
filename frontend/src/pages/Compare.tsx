import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRightLeft, Download, GitCompare, Minus, Pencil, Plus, Printer } from "lucide-react";
import { useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSearchParams } from "react-router-dom";
import { Badge, Button, Card, Empty, ErrorNote, PageHeader, inputCls } from "../components/ui";
import { api } from "../lib/api";
import { fmtDate } from "../lib/format";
import { comparisonToMarkdown, download, slug } from "../lib/export";
import type { TextChange } from "../lib/types";

const TONE: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
  ADDED: { label: "Added", cls: "border-ok/40 bg-ok/8", icon: <Plus className="size-3.5 text-ok" /> },
  REMOVED: { label: "Removed", cls: "border-bad/40 bg-bad/8", icon: <Minus className="size-3.5 text-bad" /> },
  MODIFIED: { label: "Changed", cls: "border-warn/40 bg-warn/8", icon: <Pencil className="size-3.5 text-warn" /> },
};

function Change({ c }: { c: TextChange }) {
  const t = TONE[c.change_type] ?? TONE.MODIFIED;
  return (
    <div className={`rise rounded-xl border p-3 text-sm ${t.cls}`}>
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold">{t.icon}{t.label}{c.similarity != null && <span className="font-normal text-muted">{Math.round(c.similarity * 100)}% similar</span>}</div>
      <div className="grid gap-3 md:grid-cols-2">
        <div>{c.base_text ? <><p className="mb-1 text-[11px] uppercase tracking-wide text-muted">Before · p.{c.base_page}</p><p className="line-through decoration-bad/50">{c.base_text}</p></> : <p className="text-xs text-muted">—</p>}</div>
        <div>{c.target_text ? <><p className="mb-1 text-[11px] uppercase tracking-wide text-muted">After · p.{c.target_page}</p><p>{c.target_text}</p></> : <p className="text-xs text-muted">—</p>}</div>
      </div>
    </div>
  );
}

export default function Compare() {
  const [params] = useSearchParams();
  const [base, setBase] = useState(params.get("base") ?? "");
  const [target, setTarget] = useState(params.get("target") ?? "");
  const [focus, setFocus] = useState("");
  const [filter, setFilter] = useState<string>("ALL");
  const docs = useQuery({ queryKey: ["documents", "all"], queryFn: () => api.documents({ limit: 500 }) });
  const cmp = useMutation({ mutationFn: () => api.compare(base, target, focus) });
  const submit = (e: FormEvent) => { e.preventDefault(); setFilter("ALL"); cmp.mutate(); };
  const swap = () => { setBase(target); setTarget(base); };
  const r = cmp.data;
  const shown = (r?.changes ?? []).filter((c) => filter === "ALL" || c.change_type === filter);

  const picker = (label: string, value: string, set: (v: string) => void) => (
    <label className="block min-w-0 flex-1 space-y-1.5 text-sm font-medium">{label}
      <select className={inputCls} value={value} onChange={(e) => set(e.target.value)} required>
        <option value="">Select a document…</option>
        {(docs.data?.items ?? []).map((d) => <option key={d.id} value={d.document_number}>{d.document_number} — {d.title}</option>)}
      </select></label>
  );

  return (
    <>
      <PageHeader title="Compare" subtitle="See exactly what changed between two versions, sentence by sentence." />
      <Card className="mb-6 p-5">
        <form onSubmit={submit} className="space-y-4">
          <div className="flex flex-col items-end gap-3 md:flex-row">
            {picker("Older (base)", base, setBase)}
            <Button type="button" variant="ghost" onClick={swap} aria-label="Swap documents"><ArrowRightLeft className="size-4" /></Button>
            {picker("Newer (target)", target, setTarget)}
          </div>
          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <label className="block flex-1 space-y-1.5 text-sm font-medium">Focus on a topic <span className="font-normal text-muted">(optional)</span>
              <input className={inputCls} value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="e.g. tax rates, deadlines" /></label>
            <Button type="submit" busy={cmp.isPending} disabled={!base || !target || base === target}><GitCompare className="size-4" />Compare</Button>
          </div>
          {base && base === target && <p className="text-sm text-warn">Pick two different documents.</p>}
        </form>
      </Card>

      {cmp.error ? <ErrorNote error={cmp.error} /> : null}
      {!r && !cmp.isPending && !cmp.error && <Card><Empty icon={<GitCompare className="size-6" />} title="Choose two documents" hint="The diff is computed deterministically; the AI summary can only describe changes the diff actually found." /></Card>}

      {r && (
        <div className="space-y-6">
          <div className="flex justify-end gap-2 print:hidden">
            <Button variant="ghost" size="sm" onClick={() => download(`compare-${slug(r.base.document_number)}-to-${slug(r.target.document_number)}.md`, comparisonToMarkdown(r))}><Download className="size-4" />Export Markdown</Button>
            <Button variant="ghost" size="sm" onClick={() => window.print()}><Printer className="size-4" />Print / PDF</Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            {[["Added", r.added, "text-ok"], ["Removed", r.removed, "text-bad"], ["Changed", r.modified, "text-warn"], ["Unchanged", r.unchanged_sentences, "text-muted"]].map(([k, v, c]) => (
              <Card key={k as string} className="p-4"><p className="text-xs text-muted">{k}</p><p className={`text-2xl font-bold ${c}`}>{v}</p></Card>
            ))}
          </div>
          <Card className="grid gap-4 p-5 text-sm md:grid-cols-2">
            {[r.base, r.target].map((d, i) => <div key={d.document_id}><p className="text-xs uppercase tracking-wide text-muted">{i ? "Newer" : "Older"}</p><p className="font-semibold">{d.document_number}</p><p className="text-muted">{d.title} · {fmtDate(d.issue_date)}</p></div>)}
            {r.relationship && <p className="md:col-span-2"><Badge tone="brand">{r.relationship}</Badge></p>}
          </Card>
          {r.summary_markdown && <Card className="p-5"><h2 className="mb-2 font-semibold">Summary</h2><div className="prose-answer"><ReactMarkdown remarkPlugins={[remarkGfm]}>{r.summary_markdown}</ReactMarkdown></div></Card>}
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <h2 className="mr-2 font-semibold">Changes ({r.total_changes})</h2>
              {["ALL", "ADDED", "REMOVED", "MODIFIED"].map((f) => <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-3 py-1 text-xs font-medium ${filter === f ? "bg-brand text-white" : "bg-raised text-muted hover:text-ink"}`}>{f === "ALL" ? "All" : TONE[f].label}</button>)}
            </div>
            <div className="space-y-2">{shown.map((c, i) => <Change key={i} c={c} />)}{shown.length === 0 && <p className="text-sm text-muted">No changes of this kind.</p>}</div>
            {r.changes_truncated && <p className="mt-3 text-xs text-muted">Showing the first changes only; the totals above cover the whole documents.</p>}
          </div>
        </div>
      )}
    </>
  );
}
