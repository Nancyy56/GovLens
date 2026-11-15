import type {
  Analytics, AuditPage, Bookmark, ComparisonResult, DocumentBrief, DocumentDetail, DocumentPage, HistoryDetail, HistoryPage, IngestionJob, LoginResult, PageContent,
  Principal, QueryResult, Readiness, RetrievedChunk, Role, User,
} from "./types";

const BASE = "/api/v1";
const TOKEN_KEY = "govlens.token";

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* storage blocked */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } },
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) { super(message); }
}

let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => { onUnauthorized = fn; };

function authHeaders(extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  const token = tokenStore.get();
  if (token) h.set("Authorization", `Bearer ${token}`);
  return h;
}

async function failure(res: Response): Promise<ApiError> {
  let body: any = null;
  try { body = await res.json(); } catch { /* not json */ }
  const detail = body?.detail;
  const message = typeof detail === "string" ? detail
    : Array.isArray(detail) ? detail.map((d: any) => d.msg).join("; ")
    : `Request failed (${res.status})`;
  return new ApiError(res.status, message, body);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = authHeaders(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
  if (!res.ok) throw await failure(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  login: (username: string, password: string) => request<LoginResult>("/auth/login", json({ username, password })),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<Principal>("/auth/me"),
  changePassword: (current_password: string, new_password: string) => request<void>("/auth/password", json({ current_password, new_password })),

  readiness: async (): Promise<Readiness> => {
    const res = await fetch(`${BASE}/health/ready`);
    return (await res.json()) as Readiness; // 503 still carries the per-dependency breakdown
  },

  documents: (p: { limit?: number; offset?: number; document_type?: string; status?: string; search?: string }) =>
    request<DocumentPage>(`/documents${qs(p)}`),
  document: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  page: (id: string, n: number) => request<PageContent>(`/documents/${id}/pages/${n}`),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  reingest: (id: string) => request<unknown>(`/documents/${id}/reingest`, { method: "POST" }),
  reconcile: () => request<unknown>("/documents/reconcile", { method: "POST" }),

  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<IngestionJob>("/ingest/upload?background=true", { method: "POST", body: form });
  },
  documentFile: async (id: string): Promise<Blob> => {
    const res = await fetch(`${BASE}/documents/${id}/file`, { headers: authHeaders() });
    if (res.status === 401) onUnauthorized();
    if (!res.ok) throw await failure(res);
    return res.blob();
  },
  bookmarks: () => request<Bookmark[]>("/bookmarks"),
  saveBookmark: (id: string, note?: string) => request<Bookmark>(`/bookmarks/${id}`, { method: "PUT", body: JSON.stringify({ note: note ?? null }) }),
  removeBookmark: (id: string) => request<void>(`/bookmarks/${id}`, { method: "DELETE" }),
  audit: (p: { limit?: number; offset?: number; action?: string; search?: string }) => request<AuditPage>(`/audit${qs(p)}`),
  importUrl: (url: string) => request<IngestionJob>("/ingest/url", json({ url })),
  importDomains: () => request<string[]>("/ingest/url/allowed-domains"),
  brief: (id: string, refresh = false) => request<DocumentBrief>(`/documents/${id}/brief${qs({ refresh: refresh ? "true" : undefined })}`, { method: "POST" }),
  jobs: (limit = 50) => request<IngestionJob[]>(`/ingest/jobs${qs({ limit })}`),

  query: (query: string, top_k = 10, document_numbers: string[] = []) => request<QueryResult>("/query", json({ query, top_k, document_numbers })),
  search: (query: string, top_k = 15, document_numbers: string[] = []) => request<RetrievedChunk[]>("/query/search", json({ query, top_k, document_numbers })),
  history: (p: { limit?: number; offset?: number; search?: string }) => request<HistoryPage>(`/history${qs(p)}`),
  historyItem: (id: string) => request<HistoryDetail>(`/history/${id}`),
  deleteHistory: (id: string) => request<void>(`/history/${id}`, { method: "DELETE" }),
  clearHistory: () => request<void>("/history", { method: "DELETE" }),
  feedback: (id: string, rating: -1 | 0 | 1, note?: string) => request<void>(`/history/${id}/feedback`, json({ rating, note: note ?? null })),
  analytics: (days: number) => request<Analytics>(`/analytics${qs({ days })}`),
  compare: (base: string, target: string, focus?: string) => request<ComparisonResult>("/compare", json({ base, target, focus: focus || null, summarize: true })),

  users: () => request<User[]>("/users"),
  createUser: (username: string, password: string, role: Role) => request<User>("/users", json({ username, password, role })),
  updateUser: (id: string, patch: { role?: Role; is_active?: boolean; password?: string; unlock?: boolean }) =>
    request<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteUser: (id: string) => request<void>(`/users/${id}`, { method: "DELETE" }),
};

// --- streaming answers (server-sent events over fetch, so the bearer token can be sent) ---

export type StreamEvent =
  | { event: "retrieval"; data: { retrieved_chunks: number; documents: number; supersession_warnings: unknown[] } }
  | { event: "token"; data: { text: string } }
  | { event: "done"; data: QueryResult }
  | { event: "saved"; data: { id: string } }
  | { event: "error"; data: { detail: string } };

export async function* streamQuery(
  query: string, top_k: number, document_numbers: string[], signal: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/query/stream`, {
    method: "POST", signal,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, top_k, document_numbers }),
  });
  if (res.status === 401) onUnauthorized();
  if (!res.ok || !res.body) throw await failure(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) yield { event, data: JSON.parse(data.join("\n")) } as StreamEvent;
    }
  }
}
