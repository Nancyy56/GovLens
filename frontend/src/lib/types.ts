// Types mirror the FastAPI response models (see /api/v1/openapi.json).

export type Role = "VIEWER" | "EDITOR" | "ADMIN";
export type DocumentType = "UNKNOWN" | "CIRCULAR" | "NOTIFICATION" | "ORDER" | "GAZETTE" | "POLICY" | "ADVISORY" | "REPORT";
export type DocumentStatus = "ACTIVE" | "SUPERSEDED" | "ARCHIVED";
export type RelationshipType = "SUPERSEDES" | "AMENDS" | "REFERENCES";
export type JobStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";

export const DOCUMENT_TYPES: DocumentType[] = ["CIRCULAR", "NOTIFICATION", "ORDER", "GAZETTE", "POLICY", "ADVISORY", "REPORT", "UNKNOWN"];

export interface User {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
  locked_until?: string | null;
}
export interface LoginResult { access_token: string; token_type: string; expires_at: string; user: User }
export interface Principal { user_id: string | null; username: string; role: Role; via: string }

export interface DocumentSummary {
  id: string;
  title: string;
  document_number: string;
  document_type: DocumentType;
  issue_date: string | null;
  effective_date: string | null;
  department: string | null;
  subject: string | null;
  source_url: string | null;
  file_name: string;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  chunk_count: number;
}
export interface RelatedDocument {
  relationship_id: string;
  relationship_type: RelationshipType;
  origin: "AUTO" | "MANUAL";
  document_id: string;
  document_number: string;
  document_type: DocumentType;
  status: DocumentStatus;
}
export interface DocumentDetail extends DocumentSummary {
  page_count: number;
  outgoing: RelatedDocument[];
  incoming: RelatedDocument[];
  pending_references: { referenced_number: string; relationship_type: RelationshipType }[];
}
export interface DocumentPage { items: DocumentSummary[]; total: number; limit: number; offset: number }
export interface PageContent { page_number: number; text: string }

export interface SourceCitation {
  label: string;
  document_id: string;
  document_number: string | null;
  document_type: DocumentType | null;
  page_number: number;
  issue_date: string | null;
  citation_text: string;
}
export interface SupersessionWarning {
  document_id: string;
  document_number: string | null;
  is_superseded: boolean;
  latest_document_id: string;
  latest_document_number: string | null;
  superseded_by_document_number: string | null;
}
export type SentenceStatus = "SUPPORTED" | "UNSUPPORTED" | "UNCITED" | string;
export interface SentenceCheck { text: string; citations: string[]; status: SentenceStatus; reason: string | null }
export interface VerificationReport {
  checked: number;
  supported: number;
  unsupported: number;
  uncited: number;
  all_supported: boolean;
  sentences: SentenceCheck[];
}
export interface QueryResult {
  query: string;
  answer_markdown: string;
  citations: string[];
  sources: SourceCitation[];
  supersession_warnings: SupersessionWarning[];
  verification: VerificationReport;
  citations_inferred: boolean;
}

export interface TextChange {
  change_type: "ADDED" | "REMOVED" | "MODIFIED" | string;
  base_text: string | null;
  base_page: number | null;
  target_text: string | null;
  target_page: number | null;
  similarity: number | null;
}
export interface ComparedDocument {
  document_id: string;
  document_number: string;
  document_type: DocumentType;
  title: string;
  issue_date: string | null;
  status: DocumentStatus;
}
export interface ComparisonResult {
  base: ComparedDocument;
  target: ComparedDocument;
  relationship: string | null;
  summary_markdown: string | null;
  total_changes: number;
  added: number;
  removed: number;
  modified: number;
  unchanged_sentences: number;
  changes: TextChange[];
  changes_truncated: boolean;
}

export interface IngestionJob {
  id: string;
  status: JobStatus;
  file_path: string;
  original_filename: string | null;
  document_id: string | null;
  error: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface DependencyCheck { ok: boolean; detail: string | null }
export interface Readiness { status: string; checks: Record<string, DependencyCheck> }

export interface RetrievedChunk {
  document_id: string;
  document_number: string | null;
  document_type: DocumentType | null;
  title: string | null;
  department: string | null;
  page_number: number;
  chunk_index: number;
  chunk_text: string;
  score: number;
  issue_date: string | null;
}

export interface HistoryItem {
  id: string;
  question: string;
  answer_preview: string;
  source_count: number;
  unsupported_count: number;
  feedback: number | null;
  created_at: string;
}
export interface HistoryDetail extends HistoryItem { result: QueryResult; latency_ms: number; feedback_note: string | null }
export interface HistoryPage { items: HistoryItem[]; total: number }

export interface Analytics {
  days: number;
  total_queries: number;
  unique_users: number;
  answered_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  rated: number;
  helpful: number;
  not_helpful: number;
  satisfaction: number | null;
  verified_rate: number | null;
  per_day: { day: string; queries: number; helpful: number; not_helpful: number }[];
  top_documents: { document_number: string; citations: number }[];
  flagged: { id: string; question: string; username: string; reason: string; created_at: string }[];
}

export interface DocumentBrief { document_id: string; markdown: string; pages_used: number; total_pages: number; truncated: boolean; cached: boolean }

export interface Bookmark { document_id: string; document_number: string; title: string; document_type: DocumentType; status: DocumentStatus; note: string; created_at: string; updated_at: string }
export interface AuditEntry { id: string; created_at: string; username: string; action: string; target: string | null; detail: string | null; ip: string | null }
export interface AuditPage { items: AuditEntry[]; total: number; actions: string[] }
