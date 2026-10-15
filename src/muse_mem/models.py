"""Typed objects shared by the MUSE-Mem runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SIGNAL_TYPES = {
    "user_fact", "user_state", "user_relationship", "user_preference",
    "user_feedback", "user_plan", "user_work_context", "assistant_fact",
    "task_result", "event_fact", "numeric_fact", "temporal_fact", "update_fact",
}
CONFIDENCE_VALUES = {"confirmed", "inferred", "once", "conflict"}
ENTRY_CATEGORIES = {"identity", "preference", "relationship", "goal", "context", "insight"}

@dataclass(frozen=True)
class Message:
    role: str
    content: str
    timestamp: str
    session_id: str
    message_id: str | None = None
    channel: str = "unknown"

@dataclass(frozen=True)
class Signal:
    type: str
    content: str
    confidence: str
    source_role: str
    source_time: str
    session_id: str
    source_message_id: str | None = None
    signal_id: str | None = None
    channel: str = "unknown"

@dataclass
class TopicEntry:
    entry_id: str
    file: str
    title: str
    content: str
    category: str
    confidence: str
    status: str = "active"
    source_context: str = ""
    links: list[str] = field(default_factory=list)

@dataclass
class Topic:
    path: str
    description: str
    keywords: list[str]
    entries: list[TopicEntry] = field(default_factory=list)

@dataclass
class RetrievalResult:
    answer: str
    rounds: int
    evidence: list[dict[str, Any]]
    information_residual: list[str]
    limit_reached: bool = False
