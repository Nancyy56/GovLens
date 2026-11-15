import { ExternalLink, Info } from "lucide-react";
import { Link } from "react-router-dom";

/** True for Google-style queries such as `site:sebi.gov.in circular filetype:pdf`. */
export const looksLikeWebSearch = (text: string) => /(^|\s)(site|filetype|inurl|intitle):\S+/i.test(text);

export default function WebQueryNotice({ query }: { query: string }) {
  if (!looksLikeWebSearch(query)) return null;
  return (
    <div role="note" className="rise flex items-start gap-3 rounded-xl border border-warn/30 bg-warn/10 p-3 text-sm">
      <Info className="mt-0.5 size-4 shrink-0 text-warn" />
      <div className="min-w-0 flex-1">
        <p className="font-medium">This looks like a web-search query.</p>
        <p className="mt-0.5 text-muted">GovLens only searches documents you've added, so <code className="font-mono text-xs">site:</code> and <code className="font-mono text-xs">filetype:</code> won't work here. Use it in Google to find the PDF, import it, then ask about it.</p>
        <div className="mt-2 flex flex-wrap gap-3 text-xs font-semibold text-brand">
          <a href={`https://www.google.com/search?q=${encodeURIComponent(query)}`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1">Open in Google <ExternalLink className="size-3.5" /></a>
          <Link to="/resources">Find government documents</Link>
        </div>
      </div>
    </div>
  );
}
