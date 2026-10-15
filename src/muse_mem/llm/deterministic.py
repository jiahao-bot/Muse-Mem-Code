"""Deterministic provider for tests and reproducible protocol validation."""
from __future__ import annotations

from collections import deque
from .base import LLM, LLMResponse

class DeterministicLLM(LLM):
    def __init__(self, responses: list[LLMResponse] | None = None):
        self.responses = deque(responses or [])
        self.calls: list[dict] = []

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 tool_choice: str | None = None) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools, "tool_choice": tool_choice})
        if self.responses:
            return self.responses.popleft()
        return LLMResponse("I cannot determine the answer from memory.")
