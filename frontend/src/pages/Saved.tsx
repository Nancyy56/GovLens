import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, StickyNote, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, Empty, ErrorNote, PageHeader, Skeleton, StatusBadge, useToast } from "../components/ui";
import { api } from "../lib/api";
import { timeAgo, titleCase } from "../lib/format";

export default function Saved() {
  const qc = useQueryClient();
  const toast = useToast();
  const list = useQuery({ queryKey: ["bookmarks"], queryFn: api.bookmarks });
  const remove = useMutation({ mutationFn: api.removeBookmark, onSuccess: () => { toast("ok", "Removed from Saved"); qc.invalidateQueries({ queryKey: ["bookmarks"] }); }, onError: (e: Error) => toast("bad", e.message) });
  const items = list.data ?? [];

  return (
    <>
      <PageHeader title="Saved" subtitle="Documents you've bookmarked, with your private notes." />
      {list.error ? <ErrorNote error={list.error} /> : null}
      {list.isLoading ? <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-24" />)}</div> : items.length === 0 ? (
        <Card><Empty icon={<Bookmark className="size-6" />} title="Nothing saved yet" hint="Open a document and press Save to keep it here, then add a note about why it matters." action={<Link to="/documents" className="rounded-xl bg-brand px-4 py-2 text-sm font-medium text-white">Browse documents</Link>} /></Card>
      ) : (
        <div className="space-y-3">
          {items.map((b) => (
            <Card key={b.document_id} className="rise p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <Link to={`/documents/${b.document_id}`} className="min-w-0 flex-1">
                  <p className="font-semibold hover:text-brand">{b.document_number}</p>
                  <p className="truncate text-sm text-muted">{b.title}</p>
                  <div className="mt-2 flex items-center gap-2"><Badge>{titleCase(b.document_type)}</Badge><StatusBadge status={b.status} /><span className="text-xs text-muted">saved {timeAgo(b.created_at)}</span></div>
                </Link>
                <Button variant="danger" size="sm" onClick={() => remove.mutate(b.document_id)} aria-label={`Remove ${b.document_number} from Saved`}><Trash2 className="size-4" /></Button>
              </div>
              {b.note && <p className="mt-3 flex gap-2 rounded-xl bg-raised p-3 text-sm"><StickyNote className="mt-0.5 size-4 shrink-0 text-brand" /><span className="whitespace-pre-wrap">{b.note}</span></p>}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
