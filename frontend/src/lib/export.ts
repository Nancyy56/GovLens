import type { ComparisonResult, QueryResult } from "./types";

export function download(filename: string, text: string, type = "text/markdown") {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50) || "export";

export function answerToMarkdown(question: string, r: QueryResult): string {
  const sources = r.sources.map((s) => `- **${s.label}** ${s.document_number ?? "Document"}, page ${s.page_number}: "${s.citation_text.replace(/\s+/g, " ").trim()}"`).join("\n");
  const warnings = r.supersession_warnings.map((w) => `> ⚠️ ${w.document_number} has been superseded${w.latest_document_number ? ` by ${w.latest_document_number}` : ""}.`).join("\n");
  const v = r.verification;
  return [`# ${question}`, "", warnings, "", r.answer_markdown, "", "## Sources", sources || "_None_", "",
    v.checked ? `_Verification: ${v.supported}/${v.checked} statements supported by the cited sources._` : "", "", `_Exported from GovLens on ${new Date().toLocaleString()}_`].filter((l, i, a) => l !== "" || a[i - 1] !== "").join("\n");
}

export function comparisonToMarkdown(c: ComparisonResult): string {
  const rows = c.changes.map((ch) => {
    const kind = ch.change_type.toLowerCase();
    return [`### ${kind[0].toUpperCase() + kind.slice(1)}`,
      ch.base_text ? `- **Before** (p.${ch.base_page}): ${ch.base_text}` : "", ch.target_text ? `- **After** (p.${ch.target_page}): ${ch.target_text}` : ""].filter(Boolean).join("\n");
  }).join("\n\n");
  return [`# Comparison: ${c.base.document_number} → ${c.target.document_number}`, "",
    `- **Older:** ${c.base.document_number} — ${c.base.title}`, `- **Newer:** ${c.target.document_number} — ${c.target.title}`, c.relationship ? `- **Relationship:** ${c.relationship}` : "",
    `- **Changes:** ${c.added} added, ${c.removed} removed, ${c.modified} changed, ${c.unchanged_sentences} unchanged sentences`, "",
    c.summary_markdown ? `## Summary\n\n${c.summary_markdown}\n` : "", "## Detailed changes", "", rows].filter((l) => l !== undefined).join("\n");
}
