"""Measure GovLens retrieval and answer quality against eval/dataset.json.

Usage (from the repository root, with the API running and documents ingested):
    python3 eval/run_eval.py                    # retrieval + answers (slow on CPU)
    python3 eval/run_eval.py --retrieval-only   # retrieval metrics only (fast)

Options: --base-url, --username/--password (or GOVLENS_USERNAME/GOVLENS_PASSWORD),
--api-key (or GOVLENS_API_KEY), --top-k, --dataset, --only <id>.
Uses only the Python standard library.

Metrics
- hit@k: an expected source (and page, if given) appears in the top-k chunks.
- MRR: mean of 1/rank of the first correct chunk (0 if absent).
- answer contains: every `answer_must_contain` string appears in the answer.
- abstention: questions marked `should_abstain` get the "do not contain" reply
  and no citations; answerable questions do not.
- citation precision: share of cited sources that are an expected source.
- supersession: a warning is returned when `expect_supersession_warning` is set.
- verified: share of answers whose every statement was found in the cited pages.
- links: expected supersedes/amends/references links and pending references exist.
- threshold margin: lowest reranker score of a correct chunk vs. highest score
  retrieved for unanswerable questions (shows how safe RERANKER_MIN_SCORE is).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

NO_ANSWER_TEXT = "The provided documents do not contain information about this."
ROOT = Path(__file__).resolve().parent


AUTH_HEADERS: dict[str, str] = {}


def request(base_url: str, path: str, body: dict | None, timeout: int) -> dict | list:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **AUTH_HEADERS},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def post(base_url: str, path: str, body: dict, api_key: str | None, timeout: int) -> dict | list:
    return request(base_url, path, body, timeout)


def expected_sources(item: dict) -> list[str]:
    value = item["expected_source"]
    return [v.casefold() for v in (value if isinstance(value, list) else [value])]


def chunk_matches(chunk: dict, item: dict) -> bool:
    names = [chunk.get("document_number") or "", chunk.get("file_name") or "", chunk.get("title") or ""]
    if not any(name.casefold() in expected_sources(item) for name in names if name):
        return False
    pages = item.get("expected_pages")
    return not pages or chunk["page_number"] in pages


def citation_matches(citation_text: str, item: dict) -> bool:
    return any(source in citation_text.casefold() for source in expected_sources(item))


def contains_term(text: str, term: str | list[str]) -> bool:
    haystack = text.casefold().replace(",", "")
    options = term if isinstance(term, list) else [term]
    return any(option.casefold().replace(",", "") in haystack for option in options)


def evaluate_item(item: dict, args: argparse.Namespace) -> dict:
    result: dict = {"id": item["id"], "question": item["question"]}
    body = {"query": item["question"], "top_k": args.top_k}

    started = time.perf_counter()
    chunks = post(args.base_url, "/api/v1/query/search", body, args.api_key, timeout=300)
    result["search_seconds"] = round(time.perf_counter() - started, 2)

    if "expected_source" in item:
        rank = next((i for i, chunk in enumerate(chunks, start=1) if chunk_matches(chunk, item)), None)
        result["hit"] = rank is not None
        result["reciprocal_rank"] = 1.0 / rank if rank else 0.0
        result["first_correct_rank"] = rank
        if rank:
            result["correct_chunk_score"] = round(chunks[rank - 1]["score"], 4)
    elif item.get("should_abstain"):
        result["max_retrieved_score"] = round(max((c["score"] for c in chunks), default=0.0), 4)

    if args.retrieval_only:
        return result

    started = time.perf_counter()
    answer = post(args.base_url, "/api/v1/query", body, args.api_key, timeout=args.timeout)
    result["answer_seconds"] = round(time.perf_counter() - started, 2)
    text = answer["answer_markdown"]
    citations = answer.get("citations", [])
    result["answer"] = text
    result["citations"] = citations

    abstained = NO_ANSWER_TEXT.casefold() in text.casefold()
    if item.get("should_abstain"):
        result["abstention_correct"] = abstained and not citations
        return result

    result["abstention_correct"] = not abstained
    required = item.get("answer_must_contain", [])
    result["answer_contains"] = all(contains_term(text, term) for term in required)
    result["verified"] = bool(answer.get("verification", {}).get("all_supported"))
    if citations:
        result["citation_precision"] = sum(citation_matches(c, item) for c in citations) / len(citations)
    if item.get("expect_supersession_warning"):
        result["supersession_warned"] = bool(answer.get("supersession_warnings"))
    return result


def check_links(base_url: str, dataset: dict) -> dict:
    """Verify the relationship graph that ingestion should have built."""

    expected = dataset.get("expected_links", [])
    pending = dataset.get("expected_pending", [])
    if not expected and not pending:
        return {"lines": [], "score": None}
    documents = request(base_url, "/api/v1/documents?limit=500", None, 60)["items"]
    by_number = {d["document_number"]: d["id"] for d in documents if d["document_number"]}
    details = {number: request(base_url, f"/api/v1/documents/{doc_id}", None, 60) for number, doc_id in by_number.items()}

    lines, passed, total = [], 0, 0
    for link in expected:
        total += 1
        outgoing = details.get(link["source"], {}).get("outgoing", [])
        ok = any(o["relationship_type"] == link["relationship"] and o["document_number"] == link["target"] for o in outgoing)
        passed += ok
        lines.append(f"[link {link['source']} {link['relationship']} {link['target']}] found={ok}")
    for item in pending:
        refs = details.get(item["source"], {}).get("pending_references", [])
        for number in item["numbers"]:
            total += 1
            ok = any(r["referenced_number"] == number and r["relationship_type"] == item["relationship"] for r in refs)
            passed += ok
            lines.append(f"[pending {item['source']} {item['relationship']} {number}] found={ok}")
    return {"lines": lines, "score": round(passed / total, 3) if total else None}


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def summarize(results: list[dict]) -> dict:
    def collect(key: str) -> list[float]:
        return [float(r[key]) for r in results if key in r]

    return {
        "questions": len(results),
        "hit_rate": mean(collect("hit")),
        "mrr": mean(collect("reciprocal_rank")),
        "answer_contains": mean(collect("answer_contains")),
        "abstention_accuracy": mean(collect("abstention_correct")),
        "citation_precision": mean(collect("citation_precision")),
        "supersession_warned": mean(collect("supersession_warned")),
        "verified": mean(collect("verified")),
        "min_correct_chunk_score": min(collect("correct_chunk_score"), default=None),
        "max_unanswerable_score": max(collect("max_retrieved_score"), default=None),
        "mean_search_seconds": mean(collect("search_seconds")),
        "mean_answer_seconds": mean(collect("answer_seconds")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.environ.get("GOVLENS_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("GOVLENS_API_KEY"))
    parser.add_argument("--username", default=os.environ.get("GOVLENS_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("GOVLENS_PASSWORD"))
    parser.add_argument("--dataset", default=str(ROOT / "dataset.json"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=900, help="Seconds to wait for each generated answer")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--only", action="append", help="Run only this question id (repeatable)")
    args = parser.parse_args()

    if args.api_key:
        AUTH_HEADERS["X-API-Key"] = args.api_key
    elif args.username and args.password:
        login = request(args.base_url, "/api/v1/auth/login", {"username": args.username, "password": args.password}, 30)
        AUTH_HEADERS["Authorization"] = f"Bearer {login['access_token']}"

    dataset = json.loads(Path(args.dataset).read_text())
    questions = dataset["questions"]
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]

    link_results = check_links(args.base_url, dataset)
    for line in link_results["lines"]:
        print(line, flush=True)

    results = []
    for item in questions:
        try:
            result = evaluate_item(item, args)
        except Exception as exc:  # one failed request must not end the run
            result = {"id": item["id"], "error": f"{exc.__class__.__name__}: {exc}"}
        results.append(result)
        marks = " ".join(
            f"{key}={result[key]}"
            for key in ("hit", "first_correct_rank", "answer_contains", "abstention_correct", "citation_precision", "supersession_warned", "verified", "error")
            if key in result
        )
        print(f"[{item['id']}] {marks}", flush=True)

    summary = summarize([r for r in results if "error" not in r])
    summary["links_found"] = link_results["score"]
    print("\nSUMMARY")
    for key, value in summary.items():
        print(f"  {key:22} {value}")

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_file.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"\nDetailed results: {out_file}")
    return 1 if any("error" in r for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
