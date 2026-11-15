import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookMarked, ChevronLeft, ChevronRight, FileUp, Link2, Search, UploadCloud } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import ImportDialog from "../components/ImportDialog";
import { Button, Card, Empty, ErrorNote, PageHeader, Skeleton, StatusBadge, inputCls, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, titleCase } from "../lib/format";
import { DOCUMENT_TYPES } from "../lib/types";

const PAGE = 20;

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

function UploadZone() {
  const qc = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const results = await Promise.allSettled(files.map((f) => api.upload(f)));
      const failed = results.filter((r) => r.status === "rejected") as PromiseRejectedResult[];
      if (failed.length) throw new Error(failed.map((f) => f.reason?.message).join("; "));
      return results.length;
    },
    onSuccess: (n) => { toast("ok", `${n} file${n > 1 ? "s" : ""} queued for ingestion`); qc.invalidateQueries({ queryKey: ["jobs"] }); },
    onError: (e: Error) => toast("bad", e.message),
  });
  const take = (list: FileList | null) => {
    const pdfs = [...(list ?? [])].filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return toast("bad", "Only PDF files can be uploaded");
    upload.mutate(pdfs);
  };
  const drop = (e: DragEvent) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); };

  return (
    <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={drop}
      className={`mb-6 flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed p-6 text-center transition ${over ? "border-brand bg-brand-soft" : "border-line bg-surface"}`}>
      <UploadCloud className="size-8 text-brand" />
      <p className="text-sm"><b>Drop PDFs here</b> or <button className="font-semibold text-brand underline" onClick={() => input.current?.click()}>browse</button></p>
      <p className="text-xs text-muted">Files are processed in the background; metadata, links and search index are built automatically.</p>
      <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
      {upload.isPending && <p className="text-sm text-muted">Uploading…</p>}
    </div>
  );
}

export default function Documents() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [importOpen, setImportOpen] = useState(false);
  const q = useDebounced(search);
  useEffect(() => setPage(0), [q, type, status]);

  const docs = useQuery({
    queryKey: ["documents", { q, type, status, page }],
    queryFn: () => api.documents({ limit: PAGE, offset: page * PAGE, search: q, document_type: type, status }),
    placeholderData: keepPreviousData,
  });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs(10), refetchInterval: (query) => ((query.state.data ?? []).some((j) => j.status === "PENDING" || j.status === "RUNNING") ? 2000 : false) });
  const active = (jobs.data ?? []).filter((j) => j.status === "PENDING" || j.status === "RUNNING");
  const failed = (jobs.data ?? []).filter((j) => j.status === "FAILED").slice(0, 3);
  const wasActive = useRef(0);
  useEffect(() => { if (wasActive.current > 0 && active.length === 0) qc.invalidateQueries({ queryKey: ["documents"] }); wasActive.current = active.length; }, [active.length, qc]);

  const total = docs.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <>
      <PageHeader title="Documents" subtitle={`${total} in the library`}
        actions={<>
          <Link to="/resources" className="inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium text-muted hover:bg-raised hover:text-ink"><BookMarked className="size-4" />Find documents</Link>
          {can("EDITOR") && <Button variant="soft" onClick={() => setImportOpen(true)}><Link2 className="size-4" />Import link</Button>}
        </>} />
      {can("EDITOR") && <UploadZone />}

      {active.length > 0 && (
        <Card className="mb-4 p-4"><p className="mb-2 flex items-center gap-2 text-sm font-medium"><FileUp className="size-4 text-brand" />Processing {active.length} file(s)…</p>
          <ul className="space-y-1.5 text-sm text-muted">{active.map((j) => <li key={j.id} className="flex items-center justify-between gap-2"><span className="truncate">{j.original_filename ?? j.file_path}</span><StatusBadge status={j.status} /></li>)}</ul></Card>
      )}
      {failed.map((j) => <div key={j.id} className="mb-3"><ErrorNote error={`${j.original_filename ?? "Upload"} failed: ${j.error ?? "unknown error"}`} /></div>)}

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative min-w-60 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input className={`${inputCls} pl-10`} placeholder="Search number, title, subject, department…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search documents" /></div>
        <select className={`${inputCls} w-auto`} value={type} onChange={(e) => setType(e.target.value)} aria-label="Type"><option value="">All types</option>{DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select>
        <select className={`${inputCls} w-auto`} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">Any status</option><option value="ACTIVE">Active</option><option value="SUPERSEDED">Superseded</option><option value="ARCHIVED">Archived</option></select>
      </div>

      <Card className="overflow-hidden">
        {docs.error ? <div className="p-4"><ErrorNote error={docs.error} /></div> : docs.isLoading ? <div className="space-y-px p-2">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="m-2 h-14" />)}</div>
          : (docs.data?.items ?? []).length === 0 ? <Empty icon={<FileUp className="size-6" />} title="No documents found" hint={q || type || status ? "Try clearing the filters." : "Upload a PDF, import a link, or see where to find official documents."} action={q || type || status ? undefined : <Link to="/resources" className="rounded-xl bg-brand px-4 py-2 text-sm font-medium text-white">Where do I find documents?</Link>} />
          : (
            <div className="overflow-x-auto"><table className="w-full text-sm">
              <thead className="border-b border-line bg-raised/50 text-left text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Document</th><th className="hidden px-4 py-3 md:table-cell">Type</th><th className="hidden px-4 py-3 sm:table-cell">Issued</th><th className="hidden px-4 py-3 lg:table-cell">Department</th><th className="px-4 py-3">Status</th></tr></thead>
              <tbody className="divide-y divide-line">
                {docs.data!.items.map((d) => (
                  <tr key={d.id} className="transition hover:bg-raised/60">
                    <td className="px-4 py-3"><Link to={`/documents/${d.id}`} className="block"><p className="font-medium">{d.title}</p><p className="text-xs text-muted">{d.document_number} · {d.chunk_count} chunks</p></Link></td>
                    <td className="hidden px-4 py-3 md:table-cell">{titleCase(d.document_type)}</td>
                    <td className="hidden px-4 py-3 text-muted sm:table-cell">{fmtDate(d.issue_date)}</td>
                    <td className="hidden px-4 py-3 text-muted lg:table-cell">{d.department ?? "—"}</td>
                    <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
                  </tr>
                ))}
              </tbody></table></div>
          )}
      </Card>

      {pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted">
          <span>Page {page + 1} of {pages}</span>
          <div className="flex gap-2"><Button variant="ghost" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}><ChevronLeft className="size-4" />Prev</Button>
            <Button variant="ghost" size="sm" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>Next<ChevronRight className="size-4" /></Button></div>
        </div>
      )}
      <ImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </>
  );
}
