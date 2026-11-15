import { useMutation, useQuery } from "@tanstack/react-query";
import { ExternalLink, MessageSquareText, Search as SearchIcon } from "lucide-react";
import { Fragment, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, Empty, ErrorNote, Skeleton, inputCls } from "../components/ui";
import WebQueryNotice from "../components/WebQueryNotice";
import { api } from "../lib/api";
import { fmtDate, titleCase } from "../lib/format";

const STOP = new Set(["the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "is", "are", "what", "which", "who", "how", "by", "with", "at", "be", "as"]);

/** Wrap each query word found in the text so matches stand out. */
function Highlight({ text, query }: { text: string; query: string }) {
  const words = [...new Set(query.toLowerCase().split(/\W+/).filter((w) => w.length > 2 && !STOP.has(w)))];
  if (!words.length) return <>{text}</>;
  const re = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return <>{text.split(re).map((part, i) => (i % 2 ? <mark key={i} className="rounded bg-warn/25 px-0.5 text-inherit">{part}</mark> : <Fragment key={i}>{part}</Fragment>))}</>;
}

export default function SearchPage() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [type, setType] = useState("");
  const docs = useQuery({ queryKey: ["documents", "all"], queryFn: () => api.documents({ limit: 500 }) });
  const scope = (docs.data?.items ?? []).filter((d) => !type || d.document_type === type).map((d) => d.document_number);
  const search = useMutation({ mutationFn: (q: string) => api.search(q, 20, type ? scope : []) });

  const run = (q: string) => { const t = q.trim(); if (t) { setParams({ q: t }, { replace: true }); search.mutate(t); } };
  useEffect(() => { const q = params.get("q"); if (q && !search.data && !search.isPending && !docs.isLoading) search.mutate(q); /* initial deep link */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docs.isLoading]);
  const submit = (e: FormEvent) => { e.preventDefault(); run(query); };
  const results = search.data ?? [];
  const best = Math.max(0.0001, ...results.map((r) => r.score));

  return (
    <>
      <div className="mb-6"><h1 className="text-2xl font-bold tracking-tight">Search passages</h1>
        <p className="mt-1 text-sm text-muted">Instant hybrid search (keywords + meaning) with no AI generation. Good for finding the exact wording.</p></div>

      <form onSubmit={submit} className="mb-6 flex flex-wrap gap-3">
        <div className="relative min-w-60 flex-1"><SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input className={`${inputCls} pl-10`} placeholder="e.g. penalty for late filing" value={query} onChange={(e) => setQuery(e.target.value)} autoFocus aria-label="Search query" /></div>
        <select className={`${inputCls} w-auto`} value={type} onChange={(e) => setType(e.target.value)} aria-label="Document type">
          <option value="">All types</option>{["CIRCULAR", "NOTIFICATION", "ORDER", "GAZETTE", "POLICY", "ADVISORY", "REPORT"].map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select>
        <Button type="submit" busy={search.isPending} disabled={!query.trim()}>Search</Button>
      </form>

      <div className="mb-4"><WebQueryNotice query={query} /></div>
      {search.error ? <ErrorNote error={search.error} /> : null}
      {search.isPending && <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div>}
      {search.isSuccess && results.length === 0 && <Card><Empty icon={<SearchIcon className="size-6" />} title="No matching passages" hint="Try different words, or remove the type filter." /></Card>}
      {!search.data && !search.isPending && <Card><Empty icon={<SearchIcon className="size-6" />} title="Search your library" hint="Results show the matching passage, its document and page, and a relevance bar." /></Card>}

      <div className="space-y-3">
        {results.map((r, i) => (
          <Card key={`${r.document_id}-${r.chunk_index}`} className="rise p-4" >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 flex-wrap items-center gap-2 text-sm">
                <span className="grid size-6 place-items-center rounded-md bg-brand-soft text-xs font-bold text-brand">{i + 1}</span>
                <Link to={`/documents/${r.document_id}`} className="font-semibold hover:text-brand">{r.document_number ?? "Document"}</Link>
                {r.document_type && <Badge>{titleCase(r.document_type)}</Badge>}
                <span className="text-muted">page {r.page_number} · {fmtDate(r.issue_date)}</span>
              </div>
              <div className="flex items-center gap-2" title={`Relevance ${r.score.toFixed(3)}`}>
                <div className="h-1.5 w-20 rounded-full bg-raised"><div className="h-1.5 rounded-full bg-gradient-to-r from-brand to-cyan-500" style={{ width: `${Math.max(6, (r.score / best) * 100)}%` }} /></div>
              </div>
            </div>
            {r.title && <p className="mb-1 text-xs text-muted">{r.title}{r.department ? ` · ${r.department}` : ""}</p>}
            <p className="text-sm leading-relaxed"><Highlight text={r.chunk_text} query={query} /></p>
            <div className="mt-3 flex gap-2">
              <Link to={`/documents/${r.document_id}`} className="inline-flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink"><ExternalLink className="size-3.5" />Open document</Link>
              <button onClick={() => nav(`/ask?q=${encodeURIComponent(query)}`)} className="inline-flex items-center gap-1.5 text-xs font-medium text-brand"><MessageSquareText className="size-3.5" />Ask AI about this</button>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
