import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, Skeleton } from "./ui";

/** Shows the original PDF. It is fetched with the sign-in token, then displayed from a local blob URL. */
export default function PdfViewer({ id, name }: { id: string; name: string }) {
  const file = useQuery({ queryKey: ["pdf", id], queryFn: () => api.documentFile(id), staleTime: 5 * 60_000, retry: false });
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file.data) return;
    const u = URL.createObjectURL(file.data);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file.data]);

  if (file.isLoading) return <Skeleton className="h-[70vh]" />;
  if (file.error) return <div className="p-5"><ErrorNote error={file.error} /><p className="mt-3 text-sm text-muted">The page text on the other tab still works.</p></div>;
  if (!url) return null;
  return (
    <div>
      <div className="flex items-center justify-end gap-2 border-b border-line p-3">
        <a href={url} target="_blank" rel="noreferrer noopener"><Button variant="ghost" size="sm"><ExternalLink className="size-4" />Open in new tab</Button></a>
        <a href={url} download={name}><Button variant="ghost" size="sm"><Download className="size-4" />Download</Button></a>
      </div>
      <iframe src={url} title={`Original PDF: ${name}`} className="h-[72vh] w-full bg-raised" />
    </div>
  );
}
