import { useQuery } from "@tanstack/react-query";
import { Bookmark, BookMarked, CalendarClock, FileText, GitCompare, LayoutDashboard, LogOut, MessageSquareText, Moon, Search, ShieldCheck, BarChart3, CornerDownLeft, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";

interface Item { id: string; label: string; hint?: string; icon: LucideIcon; run: () => void; group: string }

export default function CommandPalette() {
  const nav = useNavigate();
  const { logout, can } = useAuth();
  const { toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      else if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("govlens:palette", onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("govlens:palette", onOpen); };
  }, []);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => input.current?.focus(), 0); } }, [open]);

  const term = q.trim();
  const docs = useQuery({ queryKey: ["palette-docs", term], queryFn: () => api.documents({ limit: 6, search: term }), enabled: open && term.length > 1 });

  const items = useMemo<Item[]>(() => {
    const go = (to: string) => () => nav(to);
    const base: Item[] = [
      { id: "overview", label: "Overview", icon: LayoutDashboard, run: go("/"), group: "Go to" },
      { id: "ask", label: "Ask a question", icon: MessageSquareText, run: go("/ask"), group: "Go to" },
      { id: "search", label: "Search passages", icon: Search, run: go("/search"), group: "Go to" },
      { id: "docs", label: "Documents", icon: FileText, run: go("/documents"), group: "Go to" },
      { id: "compare", label: "Compare documents", icon: GitCompare, run: go("/compare"), group: "Go to" },
      { id: "saved", label: "Saved documents", icon: Bookmark, run: go("/saved"), group: "Go to" },
      { id: "timeline", label: "Timeline", icon: CalendarClock, run: go("/timeline"), group: "Go to" },
      { id: "resources", label: "Find government documents", hint: "Official sources and how to import", icon: BookMarked, run: go("/resources"), group: "Go to" },
      ...(can("ADMIN") ? [
        { id: "analytics", label: "Analytics", icon: BarChart3, run: go("/analytics"), group: "Go to" },
        { id: "admin", label: "Administration", icon: ShieldCheck, run: go("/admin"), group: "Go to" }] : []),
      { id: "theme", label: "Toggle dark mode", icon: Moon, run: toggle, group: "Actions" },
      { id: "logout", label: "Sign out", icon: LogOut, run: () => void logout(), group: "Actions" },
    ];
    const lower = term.toLowerCase();
    const filtered = term ? base.filter((i) => i.label.toLowerCase().includes(lower)) : base;
    const dynamic: Item[] = term.length > 1 ? [
      { id: "ask-q", label: `Ask: “${term}”`, hint: "AI answer with citations", icon: MessageSquareText, run: go(`/ask?q=${encodeURIComponent(term)}`), group: "Search" },
      { id: "search-q", label: `Find passages: “${term}”`, hint: "No AI, instant", icon: Search, run: go(`/search?q=${encodeURIComponent(term)}`), group: "Search" },
      ...(docs.data?.items ?? []).map((d) => ({ id: d.id, label: d.document_number, hint: d.title, icon: FileText, run: go(`/documents/${d.id}`), group: "Documents" })),
    ] : [];
    return [...dynamic, ...filtered];
  }, [term, docs.data, can, nav, toggle, logout]);

  useEffect(() => setSel(0), [term, docs.data]);
  if (!open) return null;

  const choose = (i: Item | undefined) => { if (i) { setOpen(false); i.run(); } };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(items[sel]); }
  };
  let lastGroup = "";

  return (
    <div className="fixed inset-0 z-[70] grid place-items-start justify-items-center p-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="rise relative w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl">
        <div className="flex items-center gap-3 border-b border-line px-4"><Search className="size-5 text-muted" />
          <input ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search documents, jump to a page, or ask a question…" className="h-14 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" aria-label="Command" />
          <kbd className="rounded-md border border-line px-1.5 py-0.5 text-[10px] text-muted">esc</kbd></div>
        <ul className="max-h-[50vh] overflow-auto p-2" role="listbox">
          {items.length === 0 && <li className="p-6 text-center text-sm text-muted">No results</li>}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null; lastGroup = it.group;
            return (
              <li key={it.id + i} role="option" aria-selected={i === sel}>
                {header && <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted">{header}</p>}
                <button onMouseEnter={() => setSel(i)} onClick={() => choose(it)} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${i === sel ? "bg-brand-soft text-brand" : ""}`}>
                  <it.icon className="size-4 shrink-0" /><span className="min-w-0 flex-1 truncate">{it.label}{it.hint && <span className="ml-2 text-xs text-muted">{it.hint}</span>}</span>
                  {i === sel && <CornerDownLeft className="size-4 opacity-60" />}</button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
