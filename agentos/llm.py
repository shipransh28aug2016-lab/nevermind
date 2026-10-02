"""LLM provider abstraction — offline-first, instant upgrade.

OfflineEngine (default): deterministic reasoning helpers — no network, no key.
OpenAICompatibleEngine: when the user pastes a key + base URL in Settings,
every deliberation/synthesis call upgrades to a real model. The deterministic
validators NEVER depend on the LLM (C6: code validates, LLM reasons).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class OfflineEngine:
    name = "offline-deterministic"
    available = True

    def complete(self, system: str, user: str, **_: Any) -> Dict[str, Any]:
        return {
            "text": "[offline engine] deterministic reasoning path used — "
                    "structure and facts come from validators, not from a model.",
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }


class OpenAICompatibleEngine:
    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.available = bool(api_key and base_url)

    @property
    def name(self) -> str:
        return f"openai-compatible:{self.model}"

    def complete(self, system: str, user: str, max_tokens: int = 1200,
                 temperature: float = 0.3) -> Dict[str, Any]:
        if not self.available:
            raise RuntimeError("LLM not configured")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return {"text": text, "usage": data.get("usage", {})}


def engine_from_settings(settings: Dict[str, Any]):
    llm = settings.get("llm") or {}
    if llm.get("api_key") and llm.get("base_url"):
        return OpenAICompatibleEngine(
            base_url=llm["base_url"],
            api_key=llm["api_key"],
            model=llm.get("model") or "gpt-4o-mini",
        )
    return OfflineEngine()
