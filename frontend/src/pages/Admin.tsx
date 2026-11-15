import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, RefreshCcw, Trash2, UserCog } from "lucide-react";
import { useState, type FormEvent } from "react";
import AuditLog from "../components/AuditLog";
import { Badge, Button, Card, ErrorNote, Modal, PageHeader, Skeleton, StatusBadge, inputCls, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDateTime, timeAgo } from "../lib/format";
import type { Role } from "../lib/types";

const ROLES: Role[] = ["VIEWER", "EDITOR", "ADMIN"];

function Users() {
  const qc = useQueryClient();
  const toast = useToast();
  const { user: me } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", role: "VIEWER" as Role });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users });
  const refresh = () => qc.invalidateQueries({ queryKey: ["users"] });
  const fail = (e: Error) => toast("bad", e.message);
  const create = useMutation({ mutationFn: () => api.createUser(form.username.trim(), form.password, form.role), onSuccess: () => { toast("ok", "User created"); setOpen(false); setForm({ username: "", password: "", role: "VIEWER" }); refresh(); }, onError: fail });
  const update = useMutation({ mutationFn: (v: { id: string; patch: Parameters<typeof api.updateUser>[1] }) => api.updateUser(v.id, v.patch), onSuccess: refresh, onError: fail });
  const remove = useMutation({ mutationFn: (id: string) => api.deleteUser(id), onSuccess: () => { toast("ok", "User deleted"); refresh(); }, onError: fail });

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-line p-4"><h2 className="flex items-center gap-2 font-semibold"><UserCog className="size-5 text-brand" />Users</h2><Button size="sm" onClick={() => setOpen(true)}><Plus className="size-4" />Add user</Button></div>
      {users.error ? <div className="p-4"><ErrorNote error={users.error} /></div> : users.isLoading ? <div className="p-4"><Skeleton className="h-24" /></div> : (
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="text-left text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Role</th><th className="hidden px-4 py-3 sm:table-cell">Last sign-in</th><th className="px-4 py-3">Active</th><th /></tr></thead>
          <tbody className="divide-y divide-line">{users.data!.map((u) => {
            const self = u.id === me?.user_id;
            return (<tr key={u.id}>
              <td className="px-4 py-3 font-medium">{u.username}{self && <span className="ml-2"><Badge tone="brand">you</Badge></span>}
                {u.locked_until && new Date(u.locked_until) > new Date() && <span className="ml-2 inline-flex items-center gap-2"><Badge tone="bad">locked</Badge><button className="text-xs font-semibold text-brand" onClick={() => update.mutate({ id: u.id, patch: { unlock: true } })}>Unlock</button></span>}</td>
              <td className="px-4 py-3"><select className="rounded-lg border border-line bg-surface px-2 py-1 text-sm" value={u.role} disabled={self} onChange={(e) => update.mutate({ id: u.id, patch: { role: e.target.value as Role } })} aria-label={`Role for ${u.username}`}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></td>
              <td className="hidden px-4 py-3 text-muted sm:table-cell">{fmtDateTime(u.last_login_at)}</td>
              <td className="px-4 py-3"><input type="checkbox" checked={u.is_active} disabled={self} onChange={(e) => update.mutate({ id: u.id, patch: { is_active: e.target.checked } })} aria-label={`Active: ${u.username}`} className="size-4 accent-[var(--brand)]" /></td>
              <td className="px-4 py-3 text-right"><Button variant="danger" size="sm" disabled={self} onClick={() => confirm(`Delete ${u.username}?`) && remove.mutate(u.id)} aria-label={`Delete ${u.username}`}><Trash2 className="size-4" /></Button></td></tr>);
          })}</tbody></table></div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Add user">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }} className="space-y-4">
          <label className="block space-y-1.5 text-sm font-medium">Username<input className={inputCls} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required /></label>
          <label className="block space-y-1.5 text-sm font-medium">Password<input className={inputCls} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" required /></label>
          <label className="block space-y-1.5 text-sm font-medium">Role<select className={inputCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></label>
          <p className="text-xs text-muted">Passwords need 10+ characters and cannot be common or contain the username. Viewer: ask and browse. Editor: also upload and delete. Admin: also manage users and the system.</p>
          <div className="flex justify-end"><Button type="submit" busy={create.isPending}>Create user</Button></div>
        </form>
      </Modal>
    </Card>
  );
}

function Password() {
  const toast = useToast();
  const [cur, setCur] = useState(""); const [next, setNext] = useState("");
  const { logout } = useAuth();
  const m = useMutation({ mutationFn: () => api.changePassword(cur, next), onSuccess: () => { toast("ok", "Password changed. Please sign in again."); void logout(); }, onError: (e: Error) => toast("bad", e.message) });
  return (
    <Card className="p-5">
      <h2 className="mb-4 flex items-center gap-2 font-semibold"><KeyRound className="size-5 text-brand" />Change my password</h2>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-3">
        <input className={inputCls} type="password" placeholder="Current password" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" required />
        <input className={inputCls} type="password" placeholder="New password" value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" required />
        <Button type="submit" busy={m.isPending}>Update password</Button>
      </form>
    </Card>
  );
}

function System() {
  const toast = useToast();
  const jobs = useQuery({ queryKey: ["jobs", "admin"], queryFn: () => api.jobs(30), refetchInterval: 5000 });
  const rec = useMutation({ mutationFn: api.reconcile, onSuccess: () => toast("ok", "Reconciliation finished"), onError: (e: Error) => toast("bad", e.message) });
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between"><h2 className="font-semibold">Ingestion jobs</h2>
        <Button variant="soft" size="sm" busy={rec.isPending} onClick={() => rec.mutate()}><RefreshCcw className="size-4" />Reconcile search index</Button></div>
      {(jobs.data ?? []).length === 0 ? <p className="text-sm text-muted">No jobs yet.</p> : (
        <ul className="divide-y divide-line text-sm">{(jobs.data ?? []).map((j) => (
          <li key={j.id} className="flex items-start justify-between gap-3 py-2.5"><div className="min-w-0"><p className="truncate">{j.original_filename ?? j.file_path}</p>{j.error && <p className="truncate text-xs text-bad">{j.error}</p>}</div>
            <div className="flex shrink-0 items-center gap-3 text-xs text-muted">{timeAgo(j.created_at)}<StatusBadge status={j.status} /></div></li>))}</ul>
      )}
    </Card>
  );
}

export default function Admin() {
  return (<><PageHeader title="Administration" subtitle="People, access and system maintenance." />
    <div className="space-y-6"><Users /><AuditLog /><div className="grid gap-6 lg:grid-cols-2"><System /><Password /></div></div></>);
}
