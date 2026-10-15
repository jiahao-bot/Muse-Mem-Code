"""OpenAI-compatible chat-completions provider using only the Python standard library."""
from __future__ import annotations

import json
import urllib.request
from .base import LLM, LLMResponse, ToolCall

class OpenAICompatibleLLM(LLM):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 180,
                 temperature: float = 1.0, max_tokens: int | None = None):
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key, and model are required")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 tool_choice: str | None = None) -> LLMResponse:
        payload = {"model": self.model, "temperature": self.temperature,
                   "messages": [{"role": "system", "content": system}, *messages]}
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        message = body["choices"][0]["message"]
        calls = []
        for item in message.get("tool_calls", []):
            function = item["function"]
            calls.append(ToolCall(function["name"], json.loads(function.get("arguments", "{}")), item.get("id", "")))
        return LLMResponse(message.get("content") or "", calls, message)
