import { Check, Clock, Copy, ExternalLink, FileDown, Globe2, Landmark, Link2, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, Button, Card, Empty, PageHeader, inputCls, useToast } from "../components/ui";
import ImportDialog from "../components/ImportDialog";
import { useAuth } from "../lib/auth";
import { CATEGORIES, RESOURCES, SEARCH_EXAMPLES } from "../lib/resources";

const STEPS = [
  { n: 1, title: "Find the document", text: "Open the right source below (for example CBIC for GST, RBI for banking). Use its Notifications, Circulars or Orders section." },
  { n: 2, title: "Open the PDF", text: "Click the document so the PDF opens or downloads." },
  { n: 3, title: "Copy the link or save the file", text: "Right-click the PDF link and choose Copy link address, or save the file to your computer." },
  { n: 4, title: "Bring it into GovLens", text: "Use Import link with the copied address, or Upload on the Documents page. Document numbers and replaced documents are detected automatically." },
];

export default function Resources() {
  const { can } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("All");
  const [region, setRegion] = useState<"All" | "India" | "International">("All");
  const [importOpen, setImportOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const list = useMemo(() => {
    const term = q.trim().toLowerCase();
    return RESOURCES.filter((r) => (region === "All" || r.region === region) && (cat === "All" || r.category === cat) && (!term || `${r.name} ${r.about} ${r.find} ${r.category}`.toLowerCase().includes(term)));
  }, [q, cat, region]);

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text); setCopied(text); setTimeout(() => setCopied(null), 1500); } catch { toast("bad", "Couldn't access the clipboard"); }
  };

  return (
    <>
      <PageHeader title="Find government documents" subtitle="Where to get official PDFs, and how to bring them into GovLens."
        actions={can("EDITOR") ? <Button onClick={() => setImportOpen(true)}><Link2 className="size-4" />Import link</Button> : undefined} />

      <Card className="mb-6 p-5">
        <h2 className="mb-4 flex items-center gap-2 font-semibold"><FileDown className="size-5 text-brand" />How it works</h2>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n} className="flex gap-3"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-sm font-bold text-brand">{s.n}</span>
              <div><p className="text-sm font-semibold">{s.title}</p><p className="mt-1 text-xs leading-relaxed text-muted">{s.text}</p></div></li>
          ))}
        </ol>
      </Card>

      <Card className="mb-6 p-5">
        <h2 className="mb-1 font-semibold">Search tip: find a PDF on the web</h2>
        <p className="mb-3 text-sm text-muted">These are for <b className="text-ink">Google or Bing</b>, not for GovLens. They search inside an official website to locate a PDF. Once you have the PDF, <b className="text-ink">import or upload it</b>, then ask GovLens about it. Change the words to match what you need.</p>
        <ul className="grid gap-2 md:grid-cols-2">
          {SEARCH_EXAMPLES.map((e) => (
            <li key={e.query} className="flex items-center justify-between gap-2 rounded-xl border border-line px-3 py-2">
              <div className="min-w-0"><p className="text-xs text-muted">{e.label}</p><code className="block truncate font-mono text-xs">{e.query}</code></div>
              <div className="flex shrink-0 items-center gap-1">
                <a href={`https://www.google.com/search?q=${encodeURIComponent(e.query)}`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 rounded-lg bg-brand-soft px-2.5 py-1.5 text-xs font-semibold text-brand hover:brightness-95">Open in Google <ExternalLink className="size-3.5" /></a>
                <button onClick={() => copy(e.query)} aria-label={`Copy search: ${e.label}`} className="rounded-lg p-2 text-muted hover:bg-raised hover:text-ink">{copied === e.query ? <Check className="size-4 text-ok" /> : <Copy className="size-4" />}</button>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-60 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <input className={`${inputCls} pl-10`} placeholder="Search sources (e.g. GST, banking, labour)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search sources" /></div>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Region">
        {(["All", "India", "International"] as const).map((r) => (
          <button key={r} onClick={() => { setRegion(r); setCat("All"); }} aria-pressed={region === r} className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${region === r ? "bg-ink text-bg" : "bg-raised text-muted hover:text-ink"}`}>
            {r}{r !== "All" && <span className="ml-1.5 text-xs font-normal opacity-70">{RESOURCES.filter((x) => x.region === r).length}</span>}
          </button>
        ))}
        <span className="ml-auto text-sm text-muted">{list.length} source{list.length === 1 ? "" : "s"}</span>
      </div>
      <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Category">
        {["All", ...CATEGORIES.filter((c) => region === "All" || RESOURCES.some((r) => r.category === c && r.region === region))].map((c) => (
          <button key={c} onClick={() => setCat(c)} aria-pressed={cat === c} className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition ${cat === c ? "bg-brand text-white" : "bg-raised text-muted hover:text-ink"}`}>{c}</button>
        ))}
      </div>

      {list.length === 0 ? <Card><Empty icon={<Search className="size-6" />} title="No sources match" hint="Try a different word or choose All." /></Card> : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {list.map((r) => (
            <Card key={r.url} className="rise flex flex-col p-5">
              <div className="mb-3 flex items-start justify-between gap-2">
                <span className="grid size-10 place-items-center rounded-xl bg-brand-soft text-brand">{r.region === "India" ? <Landmark className="size-5" /> : <Globe2 className="size-5" />}</span>
                <Badge tone={r.region === "India" ? "brand" : "neutral"}>{r.category}</Badge>
              </div>
              <h3 className="font-semibold leading-snug">{r.name}</h3>
              <p className="mt-1 text-sm text-muted">{r.about}</p>
              <p className="mt-3 text-sm"><span className="font-medium">You'll find: </span><span className="text-muted">{r.find}</span></p>
              {r.tip && <p className="mt-2 rounded-lg bg-raised px-3 py-2 text-xs text-muted"><b className="text-ink">Tip:</b> {r.tip}</p>}
              <div className="mt-4 flex items-center justify-between pt-1">
                <span className="flex min-w-0 items-center gap-2 text-xs text-muted"><span className="truncate">{new URL(r.url).hostname.replace(/^www\./, "")}</span>{r.slow && <span title="Reachable, but often slow or blocked from some networks" className="inline-flex shrink-0 items-center gap-1 text-warn"><Clock className="size-3" />may be slow</span>}</span>
                <a href={r.url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 rounded-xl bg-brand-soft px-3 py-1.5 text-xs font-semibold text-brand hover:brightness-95">Open site <ExternalLink className="size-3.5" /></a>
              </div>
            </Card>
          ))}
        </div>
      )}

      <p className="mt-8 text-xs leading-relaxed text-muted">These are links to official websites run by their own organisations; GovLens is not affiliated with them. Websites change and some slow down or block automated tools, so if one doesn't load, try it again in your browser or search for the document by name. Always check the official source for the latest version.</p>
      <ImportDialog open={importOpen} onClose={() => setImportOpen(false)} />
    </>
  );
}
