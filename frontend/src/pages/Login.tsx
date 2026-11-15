import { FileSearch, ShieldCheck, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Logo } from "../components/Layout";
import { Button, ErrorNote, inputCls } from "../components/ui";
import { useAuth } from "../lib/auth";

const POINTS = [
  { icon: FileSearch, text: "Hybrid search across every circular, order and gazette." },
  { icon: ShieldCheck, text: "Every sentence in an answer is checked against its cited source." },
  { icon: Sparkles, text: "Knows when a rule has been superseded, and tells you." },
];

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try { await login(username.trim(), password); } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <div className="bg-aurora grid min-h-full lg:grid-cols-2">
      <div className="hidden flex-col justify-center gap-8 p-16 lg:flex">
        <div className="flex items-center gap-3"><Logo size={44} /><span className="text-3xl font-bold tracking-tight">GovLens</span></div>
        <h2 className="max-w-md text-4xl font-bold leading-tight tracking-tight">Trustworthy answers from <span className="text-gradient">government documents</span>.</h2>
        <ul className="space-y-4">
          {POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3 text-muted"><span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-brand-soft text-brand"><Icon className="size-4" /></span>{text}</li>
          ))}
        </ul>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={submit} className="rise w-full max-w-sm space-y-4 rounded-2xl border border-line bg-surface p-8 shadow-xl">
          <div className="mb-2 flex items-center gap-3 lg:hidden"><Logo /><span className="text-xl font-bold">GovLens</span></div>
          <div><h1 className="text-xl font-bold">Sign in</h1><p className="text-sm text-muted">Use your GovLens account.</p></div>
          <label className="block space-y-1.5 text-sm font-medium">Username
            <input className={inputCls} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
          </label>
          <label className="block space-y-1.5 text-sm font-medium">Password
            <input className={inputCls} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {error ? <ErrorNote error={error} /> : null}
          <Button type="submit" busy={busy} className="w-full">Sign in</Button>
        </form>
      </div>
    </div>
  );
}
