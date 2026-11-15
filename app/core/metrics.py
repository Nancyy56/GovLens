"""Minimal Prometheus-style metrics, without an external dependency.

Exposed in the Prometheus text format at ``GET /api/v1/metrics`` (admins).
"""

from __future__ import annotations

import threading
from bisect import bisect_left
from collections.abc import Callable

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300, 600)


def _labels(names: tuple[str, ...], values: tuple[str, ...]) -> str:
    if not names:
        return ""
    escaped = (v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") for v in values)
    return "{" + ",".join(f'{n}="{v}"' for n, v in zip(names, escaped)) + "}"


class Counter:
    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = ()) -> None:
        self.name, self.help, self.label_names = name, help_text, label_names
        self._values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, *labels: str, amount: float = 1.0) -> None:
        with self._lock:
            self._values[labels] = self._values.get(labels, 0.0) + amount

    def value(self, *labels: str) -> float:
        return self._values.get(labels, 0.0)

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            for labels, value in sorted(self._values.items()):
                lines.append(f"{self.name}{_labels(self.label_names, labels)} {value:g}")
        return lines


class Histogram:
    def __init__(self, name: str, help_text: str, label_names: tuple[str, ...] = (), buckets=_LATENCY_BUCKETS) -> None:
        self.name, self.help, self.label_names, self.buckets = name, help_text, label_names, tuple(buckets)
        self._counts: dict[tuple[str, ...], list[int]] = {}
        self._sums: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, *labels: str) -> None:
        with self._lock:
            counts = self._counts.setdefault(labels, [0] * (len(self.buckets) + 1))
            counts[bisect_left(self.buckets, value)] += 1
            self._sums[labels] = self._sums.get(labels, 0.0) + value

    def count(self, *labels: str) -> int:
        return sum(self._counts.get(labels, []))

    def render(self) -> list[str]:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            for labels, counts in sorted(self._counts.items()):
                cumulative = 0
                for bound, count in zip((*self.buckets, float("inf")), counts):
                    cumulative += count
                    le = "+Inf" if bound == float("inf") else f"{bound:g}"
                    lines.append(
                        f"{self.name}_bucket{_labels((*self.label_names, 'le'), (*labels, le))} {cumulative}"
                    )
                lines.append(f"{self.name}_sum{_labels(self.label_names, labels)} {self._sums[labels]:g}")
                lines.append(f"{self.name}_count{_labels(self.label_names, labels)} {cumulative}")
        return lines


http_requests = Counter("govlens_http_requests_total", "HTTP requests by route and status", ("method", "route", "status"))
http_latency = Histogram("govlens_http_request_duration_seconds", "HTTP request latency", ("route",))
llm_requests = Counter("govlens_llm_requests_total", "LLM calls by outcome", ("outcome",))
llm_latency = Histogram("govlens_llm_duration_seconds", "LLM call latency")
ingestions = Counter("govlens_ingestions_total", "Ingestion attempts by outcome", ("outcome",))
queries = Counter("govlens_queries_total", "Answered queries by outcome", ("outcome",))

_REGISTRY = (http_requests, http_latency, llm_requests, llm_latency, ingestions, queries)


def render(gauges: dict[str, tuple[str, Callable[[], float]]] | None = None) -> str:
    """Render all metrics; ``gauges`` maps name -> (help, value function) evaluated now."""

    lines: list[str] = []
    for metric in _REGISTRY:
        lines.extend(metric.render())
    for name, (help_text, read) in (gauges or {}).items():
        try:
            value = read()
        except Exception:
            continue
        lines += [f"# HELP {name} {help_text}", f"# TYPE {name} gauge", f"{name} {value:g}"]
    return "\n".join(lines) + "\n"
