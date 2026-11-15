import { useEffect, useState } from "react";
import { Modal } from "./ui";

const ROWS: [string, string][] = [
  ["Ctrl / ⌘ + K", "Quick search and jump to anything"],
  ["?", "Show this help"],
  ["Enter", "Send your question (Shift + Enter for a new line)"],
  ["Esc", "Close a dialog or the quick search"],
];

export default function ShortcutsHelp() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if (e.key === "?" && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); setOpen(true); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <Modal open={open} onClose={() => setOpen(false)} title="Keyboard shortcuts">
      <ul className="divide-y divide-line text-sm">{ROWS.map(([k, d]) => <li key={k} className="flex items-center justify-between gap-4 py-3"><span className="text-muted">{d}</span><kbd className="shrink-0 rounded-md border border-line bg-raised px-2 py-1 text-xs font-semibold">{k}</kbd></li>)}</ul>
    </Modal>
  );
}
