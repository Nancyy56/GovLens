import clsx from "clsx";
import { BarChart3, Bookmark, BookMarked, CalendarClock, FileText, GitCompare, LayoutDashboard, LogOut, Menu, MessageSquareText, Moon, Search, ShieldCheck, Sun, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { Badge } from "./ui";
import CommandPalette from "./CommandPalette";
import ShortcutsHelp from "./ShortcutsHelp";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#6366f1" /><stop offset="1" stopColor="#06b6d4" /></linearGradient></defs>
      <rect width="32" height="32" rx="9" fill="url(#lg)" />
      <circle cx="14" cy="14" r="6" fill="none" stroke="#fff" strokeWidth="2.8" />
      <path d="M18.6 18.6l6.4 6.4" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/ask", label: "Ask", icon: MessageSquareText },
  { to: "/search", label: "Search", icon: Search },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/compare", label: "Compare", icon: GitCompare },
  { to: "/saved", label: "Saved", icon: Bookmark },
  { to: "/timeline", label: "Timeline", icon: CalendarClock },
  { to: "/resources", label: "Find documents", icon: BookMarked },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout, can } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const items = can("ADMIN") ? [...NAV, { to: "/analytics", label: "Analytics", icon: BarChart3 }, { to: "/admin", label: "Admin", icon: ShieldCheck }] : NAV;

  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}
          className={({ isActive }) => clsx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
            isActive ? "bg-brand-soft text-brand" : "text-muted hover:bg-raised hover:text-ink")}>
          <Icon className="size-[18px]" /> {label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="flex h-full bg-aurora">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-line bg-surface/70 p-4 backdrop-blur lg:flex">
        <div className="mb-8 flex items-center gap-3 px-2"><Logo /><span className="text-lg font-bold tracking-tight">GovLens</span></div>
        <button onClick={() => window.dispatchEvent(new Event("govlens:palette"))} className="mb-4 flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-sm text-muted transition hover:border-brand">
          <Search className="size-4" /><span className="flex-1 text-left">Quick search</span><kbd className="rounded border border-line px-1.5 text-[10px]">Ctrl K</kbd>
        </button>
        {nav}
        <div className="mt-auto space-y-3">
          <div className="rounded-xl bg-raised p-3 text-sm">
            <p className="truncate font-medium">{user?.username}</p>
            <div className="mt-1"><Badge tone="brand">{user?.role}</Badge></div>
          </div>
          <div className="flex gap-2">
            <button onClick={toggle} aria-label="Toggle theme" className="grid size-10 place-items-center rounded-xl text-muted hover:bg-raised hover:text-ink">
              {theme === "dark" ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
            </button>
            <button onClick={logout} className="flex flex-1 items-center justify-center gap-2 rounded-xl px-3 text-sm text-muted hover:bg-raised hover:text-ink">
              <LogOut className="size-[18px]" /> Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line bg-surface/70 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center gap-2"><Logo size={28} /><span className="font-bold">GovLens</span></div>
          <button onClick={() => setOpen(true)} aria-label="Open menu" className="rounded-lg p-2 hover:bg-raised"><Menu className="size-5" /></button>
        </header>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
            <div className="rise absolute right-0 top-0 flex h-full w-72 flex-col gap-4 bg-surface p-4">
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="self-end rounded-lg p-2 hover:bg-raised"><X className="size-5" /></button>
              {nav}
              <div className="mt-auto flex gap-2">
                <button onClick={toggle} className="rounded-xl px-3 py-2 text-sm text-muted hover:bg-raised">{theme === "dark" ? "Light" : "Dark"} mode</button>
                <button onClick={logout} className="rounded-xl px-3 py-2 text-sm text-muted hover:bg-raised">Sign out</button>
              </div>
            </div>
          </div>
        )}
        <CommandPalette />
        <ShortcutsHelp />
        <main className="min-h-0 flex-1 overflow-y-auto"><div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-8">{children}</div></main>
      </div>
    </div>
  );
}
