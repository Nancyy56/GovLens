"""Ollama HTTP client for local text generation."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core import metrics
from app.generation.interfaces import LLMClient

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """The language model backend failed or could not be reached."""


def _describe(error: Exception) -> str:
    if isinstance(error, HTTPError):
        try:
            detail = json.loads(error.read().decode()).get("error")
        except Exception:
            detail = None
        return f"Ollama returned HTTP {error.code}" + (f": {detail}" if detail else "")
    if isinstance(error, URLError):
        return f"Ollama is unreachable: {error.reason}"
    return f"Ollama request failed: {error}"


class OllamaClient(LLMClient):
    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://ollama:11434",
        timeout_seconds: int = 900,
        num_predict: int = 512,
        keep_alive: str | int | None = None,
        retries: int = 1,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.num_predict = num_predict
        self.keep_alive = keep_alive
        # Retries happen only before any output exists, e.g. when the model
        # process was killed for memory and Ollama restarts it.
        self.retries = retries

    def generate(self, prompt: str) -> str:
        started = time.perf_counter()
        data = self._post_with_retry(self._request(prompt, stream=False))
        metrics.llm_requests.inc("ok")
        metrics.llm_latency.observe(time.perf_counter() - started)
        return data["response"]

    def _post_with_retry(self, request: Request) -> dict:
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return json.loads(response.read().decode())
            except (URLError, TimeoutError, ConnectionError) as exc:
                retryable = not isinstance(exc, HTTPError) or exc.code >= 500
                if attempt < self.retries and retryable:
                    logger.warning("Ollama request failed (%s); retrying once", _describe(exc))
                    metrics.llm_requests.inc("retry")
                    time.sleep(2)
                    continue
                metrics.llm_requests.inc("error")
                raise LLMUnavailableError(_describe(exc)) from exc
        raise AssertionError("unreachable")

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield answer text as Ollama produces it."""

        started = time.perf_counter()
        attempt = 0
        while True:
            try:
                response = urlopen(self._request(prompt, stream=True), timeout=self.timeout_seconds)
                break
            except (URLError, TimeoutError, ConnectionError) as exc:
                retryable = not isinstance(exc, HTTPError) or exc.code >= 500
                if attempt < self.retries and retryable:
                    attempt += 1
                    logger.warning("Ollama stream failed to start (%s); retrying once", _describe(exc))
                    metrics.llm_requests.inc("retry")
                    time.sleep(2)
                    continue
                metrics.llm_requests.inc("error")
                raise LLMUnavailableError(_describe(exc)) from exc
        try:
            with response:
                for line in response:
                    if not line.strip():
                        continue
                    data = json.loads(line.decode())
                    if data.get("error"):
                        raise LLMUnavailableError(f"Ollama error: {data['error']}")
                    piece = data.get("response")
                    if piece:
                        yield piece
                    if data.get("done"):
                        metrics.llm_requests.inc("ok")
                        metrics.llm_latency.observe(time.perf_counter() - started)
                        return
        except (URLError, TimeoutError, ConnectionError) as exc:
            metrics.llm_requests.inc("error")
            raise LLMUnavailableError(_describe(exc)) from exc

    def generate_json(self, prompt: str, num_predict: int = 256) -> dict:
        """Ask for a JSON object (Ollama's JSON mode guarantees valid JSON syntax)."""

        started = time.perf_counter()
        request = self._request(prompt, stream=False, extra={"format": "json"}, num_predict=num_predict)
        data = self._post_with_retry(request)
        try:
            parsed = json.loads(data["response"])
        except (ValueError, KeyError) as exc:
            metrics.llm_requests.inc("error")
            raise LLMUnavailableError(f"Ollama returned invalid JSON: {exc}") from exc
        metrics.llm_requests.inc("ok")
        metrics.llm_latency.observe(time.perf_counter() - started)
        return parsed if isinstance(parsed, dict) else {}

    def ping(self) -> None:
        """Raise if Ollama is unreachable or the configured model is not pulled."""

        with urlopen(f"{self.base_url}/api/tags", timeout=5) as response:
            data = json.loads(response.read().decode())
        names = {model.get("name") for model in data.get("models", [])}
        if self.model not in names:
            raise RuntimeError(f"Model {self.model} is not available in Ollama; run `ollama pull {self.model}`")

    def warm_up(self) -> bool:
        """Load the model into memory ahead of the first question.

        Loading can take minutes on a laptop GPU. It only helps when the model is kept
        loaded afterwards, so this does nothing when keep-alive is 0.
        """

        if self.keep_alive in (None, 0, "0"):
            return False
        payload = json.dumps({"model": self.model, "keep_alive": self.keep_alive}).encode()
        request = Request(f"{self.base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=max(self.timeout_seconds, 600)) as response:
            response.read()
        return True

    def _request(self, prompt: str, stream: bool, extra: dict | None = None, num_predict: int | None = None) -> Request:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
                "think": False,
                "options": {
                    "temperature": 0,
                    "num_predict": num_predict or self.num_predict,
                },
                **({"keep_alive": self.keep_alive} if self.keep_alive is not None else {}),
                **(extra or {}),
            }
        ).encode()
        return Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
