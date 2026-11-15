import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Check, Copy, Download, FileText, History, Info, RefreshCw, Search, Send, SlidersHorizontal, Sparkles, Square, ThumbsDown, ThumbsUp, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, ErrorNote, Skeleton, inputCls, useToast } from "../components/ui";
import WebQueryNotice from "../components/WebQueryNotice";
import { api, streamQuery } from "../lib/api";
import { answerToMarkdown, download, slug } from "../lib/export";
import { timeAgo } from "../lib/format";
import type { QueryResult, SourceCitation } from "../lib/types";

interface Turn {
  id: number;
  question: string;
  answer: string;
  phase: "searching" | "writing" | "done" | "error" | "stopped";
  stats?: { chunks: number; documents: number };
  result?: QueryResult;
  error?: string;
  logId?: string;
  feedback?: -1 | 0 | 1;
}

const SUGGESTIONS = [
  "What are the latest rules on this topic?",
  "Has any circular been superseded recently?",
  "Summarise the key obligations for departments.",
  "What penalties are mentioned and on which page?",
];

// [S1] markers in the answer become clickable chips.
const linkCitations = (md: string) => md.replace(/\[(S\d+)\]/g, "[$1](#cite-$1)");

function SourcePanel({ source, onClose }: { source: SourceCitation; onClose: () => void }) {
  const page = useQuery({ queryKey: ["page", source.document_id, source.page_number], queryFn: () => api.page(source.document_id, source.page_number) });
  return (
    <Card className="rise max-h-[calc(100vh-9rem)] overflow-hidden">
      <div className="flex items-start justify-between gap-3 border-b border-line p-4">
        <div className="min-w-0">
          <Badge tone="brand">{source.label}</Badge>
          <p className="mt-2 truncate font-semibold">{source.document_number ?? "Document"}</p>
          <p className="text-xs text-muted">Page {source.page_number}</p>
        </div>
        <button onClick={onClose} aria-label="Close source" className="rounded-lg p-1 text-muted hover:bg-raised"><X className="size-5" /></button>
      </div>
      <div className="max-h-[55vh] overflow-auto p-4 text-sm leading-relaxed">
        <p className="mb-3 rounded-lg border-l-2 border-brand bg-brand-soft p-3 text-[13px]">{source.citation_text}</p>
        {page.isLoading ? <Skeleton className="h-40" /> : page.error ? <ErrorNote error={page.error} /> : <pre className="whitespace-pre-wrap font-sans text-muted">{page.data?.text}</pre>}
      </div>
      <div className="border-t border-line p-3"><Link to={`/documents/${source.document_id}`} className="flex items-center gap-2 text-sm text-brand"><FileText className="size-4" />Open document</Link></div>
    </Card>
  );
}

function HistoryPanel({ onOpen }: { onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  useEffect(() => { const t = setTimeout(() => setTerm(search), 250); return () => clearTimeout(t); }, [search]);
  const list = useQuery({ queryKey: ["history", term], queryFn: () => api.history({ limit: 40, search: term }) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["history"] });
  const del = useMutation({ mutationFn: api.deleteHistory, onSuccess: refresh, onError: (e: Error) => toast("bad", e.message) });
  const clear = useMutation({ mutationFn: api.clearHistory, onSuccess: () => { toast("ok", "History cleared"); refresh(); }, onError: (e: Error) => toast("bad", e.message) });
  const items = list.data?.items ?? [];

  return (
    <Card className="rise flex max-h-[calc(100vh-9rem)] flex-col overflow-hidden">
      <div className="space-y-3 border-b border-line p-4">
        <div className="flex items-center justify-between"><p className="font-semibold">History</p>
          {items.length > 0 && <button onClick={() => confirm("Delete all of your history?") && clear.mutate()} className="text-xs text-muted hover:text-bad">Clear all</button>}</div>
        <div className="relative"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" /><input className={`${inputCls} py-2 pl-9`} placeholder="Search past questions" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search history" /></div>
      </div>
      <div className="flex-1 overflow-auto">
        {list.isLoading ? <div className="space-y-2 p-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
          : items.length === 0 ? <p className="p-6 text-center text-sm text-muted">{term ? "No matches." : "Your questions will appear here."}</p>
          : <ul className="divide-y divide-line">{items.map((h) => (
            <li key={h.id} className="group flex items-start gap-1 p-1">
              <button onClick={() => onOpen(h.id)} className="min-w-0 flex-1 rounded-xl p-3 text-left hover:bg-raised">
                <p className="line-clamp-2 text-sm font-medium">{h.question}</p>
                <p className="mt-1 flex items-center gap-2 text-xs text-muted">{timeAgo(h.created_at)}
                  {h.feedback === 1 && <ThumbsUp className="size-3 text-ok" />}{h.feedback === -1 && <ThumbsDown className="size-3 text-bad" />}
                  {h.source_count === 0 && <Badge tone="warn">no sources</Badge>}</p>
              </button>
              <button onClick={() => del.mutate(h.id)} aria-label="Delete entry" className="mt-3 rounded-lg p-1.5 text-muted opacity-0 transition hover:bg-bad/10 hover:text-bad focus:opacity-100 group-hover:opacity-100"><Trash2 className="size-4" /></button>
            </li>))}</ul>}
      </div>
    </Card>
  );
}

function Verification({ result }: { result: QueryResult }) {
  const v = result.verification;
  if (v.checked === 0) return null;
  const clean = v.all_supported;
  return (
    <details className="group rounded-xl border border-line bg-raised/60 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5">
        {clean ? <BadgeCheck className="size-4 text-ok" /> : <AlertTriangle className="size-4 text-warn" />}
        <span className="font-medium">{clean ? "All statements trace back to the sources" : `${v.unsupported + v.uncited} statement(s) need a closer look`}</span>
        <span className="ml-auto text-xs text-muted">{v.supported}/{v.checked} supported</span>
      </summary>
      <ul className="space-y-2 border-t border-line p-3">
        {v.sentences.map((s, i) => (
          <li key={i} className="flex gap-2">
            <Badge tone={s.status === "SUPPORTED" ? "ok" : "warn"}>{s.status}</Badge>
            <span className="text-muted">{s.text}{s.reason ? <em className="block text-xs">{s.reason}</em> : null}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function Answer({ turn, onCite }: { turn: Turn; onCite: (label: string) => void }) {
  const writing = turn.phase === "writing";
  return (
    <div className="prose-answer">
      {turn.phase === "searching" && <p className="flex items-center gap-2 text-sm text-muted"><Sparkles className="size-4 animate-pulse text-brand" />Searching the library…</p>}
      <div className={writing ? "caret" : ""}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          urlTransform={(u) => u}
          components={{
            a: ({ href, children }) => {
              const m = href?.match(/^#cite-(S\d+)$/);
              if (m) return <button onClick={() => onCite(m[1])} className="mx-0.5 rounded-md bg-brand-soft px-1.5 py-0.5 align-baseline text-xs font-semibold text-brand hover:brightness-95">{children}</button>;
              return <a href={href} target="_blank" rel="noreferrer noopener" className="text-brand underline">{children}</a>;
            },
          }}
        >{linkCitations(turn.answer)}</ReactMarkdown>
      </div>
    </div>
  );
}

function Actions({ turn, onRegenerate, onFeedback }: { turn: Turn; onRegenerate: () => void; onFeedback: (r: -1 | 0 | 1) => void }) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const r = turn.result;
  if (!r) return null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(answerToMarkdown(turn.question, r)); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { toast("bad", "Couldn't access the clipboard"); }
  };
  const btn = "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted transition hover:bg-raised hover:text-ink";
  return (
    <div className="flex flex-wrap items-center gap-1 border-t border-line pt-3">
      <button onClick={copy} className={btn}>{copied ? <Check className="size-3.5 text-ok" /> : <Copy className="size-3.5" />}{copied ? "Copied" : "Copy"}</button>
      <button onClick={() => download(`${slug(turn.question)}.md`, answerToMarkdown(turn.question, r))} className={btn}><Download className="size-3.5" />Export</button>
      <button onClick={onRegenerate} className={btn}><RefreshCw className="size-3.5" />Regenerate</button>
      {turn.logId && (
        <span className="ml-auto flex items-center gap-1" role="group" aria-label="Rate this answer">
          <span className="mr-1 text-xs text-muted">Helpful?</span>
          <button onClick={() => onFeedback(turn.feedback === 1 ? 0 : 1)} aria-pressed={turn.feedback === 1} aria-label="Helpful" className={`${btn} ${turn.feedback === 1 ? "!bg-ok/15 !text-ok" : ""}`}><ThumbsUp className="size-3.5" /></button>
          <button onClick={() => onFeedback(turn.feedback === -1 ? 0 : -1)} aria-pressed={turn.feedback === -1} aria-label="Not helpful" className={`${btn} ${turn.feedback === -1 ? "!bg-bad/15 !text-bad" : ""}`}><ThumbsDown className="size-3.5" /></button>
        </span>
      )}
    </div>
  );
}

export default function Ask() {
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const toast = useToast();
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [topK, setTopK] = useState(10);
  const [scope, setScope] = useState<string[]>([]);
  const [showOpts, setShowOpts] = useState(false);
  const [active, setActive] = useState<SourceCitation | null>(null);
  const [side, setSide] = useState<"source" | "history">("history");
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const docs = useQuery({ queryKey: ["documents", "all"], queryFn: () => api.documents({ limit: 500 }) });
  const busy = turns.some((t) => t.phase === "searching" || t.phase === "writing");

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns.length, turns[turns.length - 1]?.answer.length]);
  useEffect(() => () => abort.current?.abort(), []);

  const sourcesOf = useMemo(() => {
    const map = new Map<number, Record<string, SourceCitation>>();
    for (const t of turns) map.set(t.id, Object.fromEntries((t.result?.sources ?? []).map((s) => [s.label, s])));
    return map;
  }, [turns]);

  const patch = (id: number, p: Partial<Turn> | ((t: Turn) => Partial<Turn>)) =>
    setTurns((all) => all.map((t) => (t.id === id ? { ...t, ...(typeof p === "function" ? p(t) : p) } : t)));

  const ask = useCallback(async (question: string, scopeOverride?: string[]) => {
    const q = question.trim();
    if (!q) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, question: q, answer: "", phase: "searching" }]);
    setInput(""); setActive(null);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      for await (const ev of streamQuery(q, topK, scopeOverride ?? scope, ctrl.signal)) {
        if (ev.event === "retrieval") patch(id, { stats: { chunks: ev.data.retrieved_chunks, documents: ev.data.documents } });
        else if (ev.event === "token") patch(id, (t) => ({ answer: t.answer + ev.data.text, phase: "writing" }));
        else if (ev.event === "done") patch(id, { result: ev.data, answer: ev.data.answer_markdown, phase: "done" });
        else if (ev.event === "saved") { patch(id, { logId: ev.data.id }); qc.invalidateQueries({ queryKey: ["history"] }); }
        else if (ev.event === "error") patch(id, { phase: "error", error: ev.data.detail });
      }
      patch(id, (t) => (t.phase === "writing" || t.phase === "searching" ? { phase: "done" } : {}));
    } catch (e) {
      if ((e as Error).name === "AbortError") patch(id, { phase: "stopped" });
      else patch(id, { phase: "error", error: e instanceof Error ? e.message : "Something went wrong" });
    }
  }, [topK, scope, qc]);

  // Deep link: /ask?q=... (used by the command palette and the search page).
  const started = useRef(false);
  useEffect(() => {
    const q = params.get("q");
    const doc = params.get("doc");
    if (doc && !started.current) setScope([doc]);
    if (q && !started.current) {
      started.current = true; setParams({}, { replace: true });
      // Wait one tick so a ?doc= scope is applied before the question is sent.
      setTimeout(() => void ask(q, doc ? [doc] : undefined), 0);
    }
  }, [params, setParams, ask]);

  async function openHistory(id: string) {
    try {
      const h = await api.historyItem(id);
      setActive(null);
      setTurns((t) => [...t, { id: Date.now(), question: h.question, answer: h.result.answer_markdown, phase: "done", result: h.result, logId: h.id, feedback: (h.feedback ?? 0) as -1 | 0 | 1 }]);
    } catch (e) { toast("bad", e instanceof Error ? e.message : "Couldn't open that answer"); }
  }

  async function rate(t: Turn, rating: -1 | 0 | 1) {
    if (!t.logId) return;
    patch(t.id, { feedback: rating });
    try {
      await api.feedback(t.logId, rating);
      if (rating === -1) toast("ok", "Thanks, we'll use this to improve answers");
      qc.invalidateQueries({ queryKey: ["history"] });
    } catch (e) { patch(t.id, { feedback: t.feedback }); toast("bad", e instanceof Error ? e.message : "Couldn't save feedback"); }
  }

  const submit = (e: FormEvent) => { e.preventDefault(); if (!busy) void ask(input); };
  const showSource = (s: SourceCitation) => { setActive(s); setSide("source"); };

  const sidebar = side === "source" && active ? <SourcePanel source={active} onClose={() => { setActive(null); setSide("history"); }} /> : <HistoryPanel onOpen={openHistory} />;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
      <div className="flex min-h-[calc(100vh-9rem)] flex-col">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div><h1 className="text-2xl font-bold tracking-tight">Ask GovLens</h1>
            <p className="mt-1 text-sm text-muted">Answers are written only from your documents, with every claim cited and checked.</p></div>
          {turns.length > 0 && <Button variant="ghost" size="sm" onClick={() => { abort.current?.abort(); setTurns([]); setActive(null); }}>New chat</Button>}
        </div>

        <div className="flex-1 space-y-8">
          {turns.length === 0 && (
            <Card className="p-8 text-center">
              <div className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-brand-soft text-brand"><Sparkles className="size-6" /></div>
              <p className="font-semibold">What would you like to know?</p>
              <div className="mx-auto mt-5 grid max-w-xl gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => <button key={s} onClick={() => ask(s)} className="rounded-xl border border-line p-3 text-left text-sm text-muted transition hover:border-brand hover:text-ink">{s}</button>)}
              </div>
            </Card>
          )}

          {turns.map((t) => {
            const lookup = sourcesOf.get(t.id) ?? {};
            return (
              <section key={t.id} className="space-y-3">
                <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm text-white">{t.question}</div>
                <Card className="space-y-4 p-5">
                  {(t.result?.supersession_warnings ?? []).map((w) => (
                    <div key={w.document_id} className="flex items-start gap-2 rounded-xl border border-warn/30 bg-warn/10 p-3 text-sm">
                      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warn" />
                      <span><b>{w.document_number}</b> has been superseded{w.latest_document_number ? <> by <b>{w.latest_document_number}</b></> : null}. Check the newer document before relying on this.</span>
                    </div>
                  ))}
                  {t.phase === "error" ? <ErrorNote error={t.error} /> : <Answer turn={t} onCite={(l) => lookup[l] && showSource(lookup[l])} />}
                  {t.phase === "stopped" && <p className="text-xs text-muted">Stopped.</p>}
                  {t.result && t.result.sources.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Sources{t.result.citations_inferred ? " (all retrieved)" : ""}</p>
                      <div className="flex flex-wrap gap-2">
                        {t.result.sources.map((s) => (
                          <button key={s.label} onClick={() => showSource(s)} className="flex items-center gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs transition hover:border-brand">
                            <span className="font-semibold text-brand">{s.label}</span><span>{s.document_number ?? "Doc"} · p.{s.page_number}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {t.phase === "done" && t.result && t.result.sources.length === 0 && (
                    <div className="flex items-start gap-2 rounded-xl bg-raised p-3 text-sm text-muted">
                      <Info className="mt-0.5 size-4 shrink-0 text-brand" />
                      <span>Your library may not contain a document that answers this. <Link to="/resources" className="font-semibold text-brand">Find and import the official PDF</Link>, then ask again.</span>
                    </div>
                  )}
                  {t.result && <Verification result={t.result} />}
                  {t.stats && t.phase === "done" && <p className="text-xs text-muted">Read {t.stats.chunks} passages from {t.stats.documents} document(s).</p>}
                  {t.phase === "done" && <Actions turn={t} onRegenerate={() => !busy && ask(t.question)} onFeedback={(r) => rate(t, r)} />}
                </Card>
              </section>
            );
          })}
          <div ref={bottom} />
        </div>

        <form onSubmit={submit} className="sticky bottom-0 mt-6 space-y-2 bg-gradient-to-t from-bg via-bg to-transparent pb-2 pt-4">
          {showOpts && (
            <Card className="rise space-y-4 p-4 text-sm">
              <label className="block"><span className="font-medium">Passages to read: {topK}</span><input type="range" min={3} max={30} value={topK} onChange={(e) => setTopK(+e.target.value)} className="mt-2 w-full accent-[var(--brand)]" /></label>
              <label className="block"><span className="font-medium">Limit to documents</span>
                <select multiple value={scope} onChange={(e) => setScope([...e.target.selectedOptions].map((o) => o.value))} className={`${inputCls} mt-2 h-28`}>
                  {(docs.data?.items ?? []).map((d) => <option key={d.id} value={d.document_number}>{d.document_number} — {d.title}</option>)}
                </select>
                <span className="mt-1 block text-xs text-muted">{scope.length ? `${scope.length} selected` : "All documents"} · Ctrl/⌘-click to pick several</span>
              </label>
            </Card>
          )}
          <WebQueryNotice query={input} />
          {scope.length > 0 && !showOpts && (
            <div className="flex flex-wrap items-center gap-2 text-xs"><span className="text-muted">Searching only in:</span>
              {scope.map((n) => <span key={n} className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-2.5 py-1 font-semibold text-brand">{n}<button type="button" onClick={() => setScope((c) => c.filter((x) => x !== n))} aria-label={`Stop limiting to ${n}`}><X className="size-3" /></button></span>)}</div>
          )}
          <div className="flex items-end gap-2 rounded-2xl border border-line bg-surface p-2 shadow-lg focus-within:border-brand">
            <button type="button" onClick={() => setShowOpts((s) => !s)} aria-label="Search options" className={`rounded-xl p-2.5 ${showOpts || scope.length ? "bg-brand-soft text-brand" : "text-muted hover:bg-raised"}`}><SlidersHorizontal className="size-5" /></button>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={1} placeholder="Ask about a circular, order, or policy…"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy) void ask(input); } }}
              className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted" aria-label="Your question" />
            {busy ? <Button type="button" variant="soft" onClick={() => abort.current?.abort()} aria-label="Stop"><Square className="size-4" />Stop</Button>
              : <Button type="submit" disabled={!input.trim()} aria-label="Send"><Send className="size-4" /></Button>}
          </div>
        </form>
      </div>

      <aside className="hidden lg:block">
        <div className="sticky top-4 space-y-3">
          <div className="flex gap-1 rounded-xl bg-raised p-1 text-sm font-medium" role="tablist">
            <button role="tab" aria-selected={side === "history"} onClick={() => setSide("history")} className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-1.5 ${side === "history" ? "bg-surface shadow-sm" : "text-muted"}`}><History className="size-4" />History</button>
            <button role="tab" aria-selected={side === "source"} onClick={() => active && setSide("source")} disabled={!active} className={`flex flex-1 items-center justify-center gap-2 rounded-lg py-1.5 disabled:opacity-40 ${side === "source" ? "bg-surface shadow-sm" : "text-muted"}`}><FileText className="size-4" />Source</button>
          </div>
          {sidebar}
        </div>
      </aside>
      {active && <div className="lg:hidden"><SourcePanel source={active} onClose={() => setActive(null)} /></div>}
    </div>
  );
}
