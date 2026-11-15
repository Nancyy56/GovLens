import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Bookmark, BookmarkCheck, FileText, GitCompare, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Badge, Button, Card, ErrorNote, Modal, PageHeader, Skeleton, StatusBadge, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, titleCase } from "../lib/format";
import type { RelatedDocument } from "../lib/types";
import LineageGraph from "../components/LineageGraph";
import PdfViewer from "../components/PdfViewer";
import { inputCls } from "../components/ui";

const VERB = { SUPERSEDES: "supersedes", AMENDS: "amends", REFERENCES: "references" } as const;

function Related({ title, items, incoming }: { title: string; items: RelatedDocument[]; incoming?: boolean }) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <ul className="space-y-2">
        {items.map((r) => (
          <li key={r.relationship_id}><Link to={`/documents/${r.document_id}`} className="flex items-center justify-between gap-3 rounded-xl border border-line p-3 text-sm transition hover:border-brand">
            <span className="flex items-center gap-2">{incoming ? <ArrowLeft className="size-4 text-muted" /> : <ArrowRight className="size-4 text-muted" />}
              <b>{r.document_number}</b><Badge tone={r.relationship_type === "SUPERSEDES" ? "warn" : "neutral"}>{incoming ? `${VERB[r.relationship_type]} this` : VERB[r.relationship_type]}</Badge>
              {r.origin === "MANUAL" && <Badge tone="brand">manual</Badge>}</span>
            <StatusBadge status={r.status} />
          </Link></li>
        ))}
      </ul>
    </div>
  );
}

export default function DocumentView() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();
  const [pageNo, setPageNo] = useState(1);
  const [confirm, setConfirm] = useState(false);
  const [view, setView] = useState<"text" | "pdf">("text");
  const [note, setNote] = useState<string | null>(null);
  const doc = useQuery({ queryKey: ["document", id], queryFn: () => api.document(id) });
  const text = useQuery({ queryKey: ["page", id, pageNo], queryFn: () => api.page(id, pageNo), enabled: !!doc.data });

  const del = useMutation({ mutationFn: () => api.deleteDocument(id), onSuccess: () => { toast("ok", "Document deleted"); qc.invalidateQueries({ queryKey: ["documents"] }); nav("/documents"); }, onError: (e: Error) => toast("bad", e.message) });
  const saved = useQuery({ queryKey: ["bookmarks"], queryFn: api.bookmarks });
  const mine = (saved.data ?? []).find((b) => b.document_id === id);
  const refreshSaved = () => qc.invalidateQueries({ queryKey: ["bookmarks"] });
  const toggleSave = useMutation({ mutationFn: async (): Promise<void> => { if (mine) await api.removeBookmark(id); else await api.saveBookmark(id); }, onSuccess: () => { toast("ok", mine ? "Removed from Saved" : "Saved"); setNote(null); refreshSaved(); }, onError: (e: Error) => toast("bad", e.message) });
  const saveNote = useMutation({ mutationFn: (text: string) => api.saveBookmark(id, text), onSuccess: () => { toast("ok", "Note saved"); setNote(null); refreshSaved(); }, onError: (e: Error) => toast("bad", e.message) });
  const brief = useMutation({ mutationFn: (refresh: boolean) => api.brief(id, refresh), onError: (e: Error) => toast("bad", e.message) });
  const reingest = useMutation({ mutationFn: () => api.reingest(id), onSuccess: () => { toast("ok", "Re-ingested"); qc.invalidateQueries({ queryKey: ["document", id] }); }, onError: (e: Error) => toast("bad", e.message) });

  if (doc.isLoading) return <div className="space-y-3"><Skeleton className="h-10 w-80" /><Skeleton className="h-72" /></div>;
  if (doc.error || !doc.data) return <ErrorNote error={doc.error ?? "Not found"} />;
  const d = doc.data;
  const meta: [string, string][] = [["Number", d.document_number], ["Type", titleCase(d.document_type)], ["Issued", fmtDate(d.issue_date)], ["Effective", fmtDate(d.effective_date)], ["Department", d.department ?? "—"], ["Subject", d.subject ?? "—"], ["Pages", String(d.page_count)], ["Chunks", String(d.chunk_count)]];

  return (
    <>
      <Link to="/documents" className="mb-4 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" />Documents</Link>
      <PageHeader title={d.title} subtitle={d.file_name}
        actions={<>
          {(() => {
            const replaces = d.outgoing.find((r) => r.relationship_type === "SUPERSEDES");
            const replacedBy = d.incoming.find((r) => r.relationship_type === "SUPERSEDES");
            const href = replaces ? `/compare?base=${encodeURIComponent(replaces.document_number)}&target=${encodeURIComponent(d.document_number)}`
              : replacedBy ? `/compare?base=${encodeURIComponent(d.document_number)}&target=${encodeURIComponent(replacedBy.document_number)}`
              : `/compare?base=${encodeURIComponent(d.document_number)}`;
            return <Link to={href} className="inline-flex items-center gap-2 rounded-xl bg-brand-soft px-4 py-2.5 text-sm font-medium text-brand"><GitCompare className="size-4" />{replaces ? `Compare with ${replaces.document_number}` : replacedBy ? `Compare with ${replacedBy.document_number}` : "Compare"}</Link>;
          })()}
          <Button variant={mine ? "soft" : "ghost"} busy={toggleSave.isPending} onClick={() => toggleSave.mutate()} aria-pressed={!!mine}>{mine ? <BookmarkCheck className="size-4" /> : <Bookmark className="size-4" />}{mine ? "Saved" : "Save"}</Button>
          <Link to={`/ask?doc=${encodeURIComponent(d.document_number)}&q=${encodeURIComponent(`Summarise ${d.document_number}`)}`} className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-muted hover:bg-raised hover:text-ink"><FileText className="size-4" />Ask about it</Link>
          {can("EDITOR") && <Button variant="ghost" busy={reingest.isPending} onClick={() => reingest.mutate()}><RefreshCw className="size-4" />Re-ingest</Button>}
          {can("EDITOR") && <Button variant="danger" onClick={() => setConfirm(true)}><Trash2 className="size-4" />Delete</Button>}
        </>} />
      <div className="mb-4"><StatusBadge status={d.status} /></div>

      {d.status === "SUPERSEDED" && d.incoming.some((r) => r.relationship_type === "SUPERSEDES") && (
        <div className="mb-4 rounded-xl border border-warn/30 bg-warn/10 p-3 text-sm">This document has been superseded by <b>{d.incoming.find((r) => r.relationship_type === "SUPERSEDES")?.document_number}</b>.</div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6">
          <Card className="p-5"><dl className="space-y-3 text-sm">{meta.map(([k, v]) => <div key={k} className="flex justify-between gap-4"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>)}</dl></Card>
          <Card className="space-y-5 p-5">
            <h2 className="font-semibold">Lineage</h2>
            <Related title="This document" items={d.outgoing} />
            <Related title="Other documents" items={d.incoming} incoming />
            {d.pending_references.length > 0 && <div><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Mentioned, not yet uploaded</h3>
              <div className="flex flex-wrap gap-2">{d.pending_references.map((p) => <Badge key={p.referenced_number + p.relationship_type}>{p.referenced_number}</Badge>)}</div></div>}
            {!d.outgoing.length && !d.incoming.length && !d.pending_references.length && <p className="text-sm text-muted">No relationships detected.</p>}
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-2">
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 font-semibold"><Sparkles className="size-5 text-brand" />Plain-language brief</h2>
            {brief.data ? <Button variant="ghost" size="sm" busy={brief.isPending} onClick={() => brief.mutate(true)}><RefreshCw className="size-4" />Rewrite</Button>
              : <Button variant="soft" size="sm" busy={brief.isPending} onClick={() => brief.mutate(false)}><Sparkles className="size-4" />Generate brief</Button>}
          </div>
          {!brief.data && !brief.isPending && <p className="mt-2 text-sm text-muted">Who is affected, what must be done, deadlines and penalties, in a few lines, with page references.</p>}
          {brief.isPending && <div className="mt-4 space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" /></div>}
          {brief.error ? <div className="mt-3"><ErrorNote error={brief.error} /></div> : null}
          {brief.data && (
            <div className="rise mt-3">
              <div className="prose-answer"><ReactMarkdown remarkPlugins={[remarkGfm]}>{brief.data.markdown}</ReactMarkdown></div>
              <p className="mt-2 text-xs text-muted">AI-written from the document text{brief.data.truncated ? ` (first ${brief.data.pages_used} of ${brief.data.total_pages} pages, as the document is long)` : ""}. Check the pages cited before relying on it.{brief.data.cached ? " Saved result." : ""}</p>
            </div>
          )}
        </Card>
        {mine && (
          <Card className="p-5">
            <h2 className="mb-2 font-semibold">My note <span className="text-xs font-normal text-muted">(private)</span></h2>
            <textarea className={`${inputCls} min-h-24`} value={note ?? mine.note} onChange={(e) => setNote(e.target.value)} placeholder="Why this matters, what to follow up…" maxLength={4000} aria-label="My note" />
            {note !== null && note !== mine.note && <div className="mt-3 flex justify-end gap-2"><Button variant="ghost" size="sm" onClick={() => setNote(null)}>Cancel</Button><Button size="sm" busy={saveNote.isPending} onClick={() => saveNote.mutate(note)}>Save note</Button></div>}
          </Card>
        )}
        {(d.outgoing.length > 0 || d.incoming.length > 0) && (
          <Card className="p-5"><h2 className="mb-3 font-semibold">Lineage graph</h2><LineageGraph doc={d} />
            <p className="mt-2 text-xs text-muted">Arrows point from the document that acts to the document it acts on. Click a node to open it.</p></Card>
        )}
        <Card>
          <div className="flex items-center justify-between border-b border-line p-4">
            <div className="flex gap-1 rounded-xl bg-raised p-1 text-sm font-medium" role="tablist">
              <button role="tab" aria-selected={view === "text"} onClick={() => setView("text")} className={`rounded-lg px-3 py-1.5 ${view === "text" ? "bg-surface shadow-sm" : "text-muted"}`}>Page text</button>
              <button role="tab" aria-selected={view === "pdf"} onClick={() => setView("pdf")} className={`rounded-lg px-3 py-1.5 ${view === "pdf" ? "bg-surface shadow-sm" : "text-muted"}`}>Original PDF</button>
            </div>
            {view === "text" && <div className="flex items-center gap-2 text-sm">
              <Button variant="ghost" size="sm" disabled={pageNo <= 1} onClick={() => setPageNo((p) => p - 1)}>Prev</Button>
              <span className="tabular-nums text-muted">{pageNo} / {d.page_count || 1}</span>
              <Button variant="ghost" size="sm" disabled={pageNo >= d.page_count} onClick={() => setPageNo((p) => p + 1)}>Next</Button>
            </div>}
          </div>
          {view === "pdf" ? <PdfViewer id={id} name={d.file_name} /> : <div className="max-h-[70vh] overflow-auto p-5">{text.isLoading ? <Skeleton className="h-64" /> : text.error ? <ErrorNote error={text.error} /> : <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{text.data?.text}</pre>}</div>}
        </Card>
        </div>
      </div>

      <Modal open={confirm} onClose={() => setConfirm(false)} title="Delete this document?">
        <p className="mb-5 text-sm text-muted">This removes <b>{d.document_number}</b> and its search index. It cannot be undone.</p>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setConfirm(false)}>Cancel</Button><Button variant="danger" busy={del.isPending} onClick={() => del.mutate()}>Delete</Button></div>
      </Modal>
    </>
  );
}
