from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.generation.interfaces import LLMClient


class OllamaClient(LLMClient):
    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://ollama:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 512
                }
            }
        ).encode()

        req = Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urlopen(req, timeout=900) as response:
            data = json.loads(response.read().decode())

        return data["response"]