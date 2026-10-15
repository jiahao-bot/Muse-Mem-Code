"""LLM provider contract used by all three Gates."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str = ""

@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_message: dict[str, Any] | None = None

class LLM(ABC):
    @abstractmethod
    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                 tool_choice: str | None = None) -> LLMResponse:
        raise NotImplementedError
