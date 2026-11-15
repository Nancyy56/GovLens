import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib/api";
import { Button, ErrorNote, Modal, inputCls, useToast } from "./ui";

export default function ImportDialog({ open, onClose, initialUrl = "" }: { open: boolean; onClose: () => void; initialUrl?: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [url, setUrl] = useState(initialUrl);
  const domains = useQuery({ queryKey: ["import-domains"], queryFn: api.importDomains, enabled: open, staleTime: Infinity });
  const run = useMutation({
    mutationFn: () => api.importUrl(url.trim()),
    onSuccess: (job) => {
      toast("ok", `Downloaded ${job.original_filename ?? "the PDF"}. It is being indexed now.`);
      qc.invalidateQueries({ queryKey: ["jobs"] });
      setUrl(""); onClose();
    },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); run.mutate(); };
  const any = domains.data?.includes("*");

  return (
    <Modal open={open} onClose={() => { run.reset(); onClose(); }} title="Import a PDF from a link">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted">Paste the direct link to a PDF on an official government website. GovLens downloads it and builds the search index, so you don't have to save and upload it yourself.</p>
        <label className="block space-y-1.5 text-sm font-medium">PDF link
          <input className={inputCls} type="url" inputMode="url" placeholder="https://www.cbic.gov.in/.../notification.pdf" value={url} onChange={(e) => setUrl(e.target.value)} autoFocus required />
        </label>
        {run.error ? <ErrorNote error={run.error} /> : null}
        <div className="flex items-start gap-2 rounded-xl bg-raised p-3 text-xs text-muted">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-ok" />
          <span>For safety, only links on approved sites are accepted{any ? " (an administrator has allowed any public site)" : domains.data ? `: ${domains.data.map((d) => "." + d).join("  ")}` : ""}. Internal network addresses are always refused. Not on the list? Download the PDF and use Upload.</span>
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={run.isPending} disabled={!url.trim()}><Link2 className="size-4" />Import</Button>
        </div>
      </form>
    </Modal>
  );
}
