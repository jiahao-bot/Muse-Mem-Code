"""Perception Gate: instruction-conditioned evidence selection."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from ..llm import LLM
from ..models import Message, Signal
from ..storage import EpisodicMemory

class PerceptionGate:
    def __init__(self, llm: LLM, episodic: EpisodicMemory, prompt_path: str):
        self.llm = llm
        self.episodic = episodic
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")

    @staticmethod
    def _source_indices(content: str, messages: list[Message]) -> list[int]:
        metadata = dict(re.findall(r"(source_role|source_time|turn|session_context)=([^;\]]+)", content))
        candidates = list(range(len(messages)))
        if metadata.get("source_role") and metadata["source_role"] != "unknown":
            candidates = [i for i in candidates if messages[i].role == metadata["source_role"].strip()]
        if metadata.get("source_time") and metadata["source_time"] != "unknown":
            source_time = metadata["source_time"].strip()
            candidates = [i for i in candidates if messages[i].timestamp == source_time]
        if metadata.get("session_context") and metadata["session_context"] not in {"unknown", "..."}:
            session = metadata["session_context"].strip()
            candidates = [i for i in candidates if messages[i].session_id == session]
        if metadata.get("turn") and metadata["turn"].strip().isdigit():
            turn = int(metadata["turn"].strip())
            for index in (turn, turn - 1):
                if 0 <= index < len(messages) and index in candidates:
                    return [index]
        evidence = content.split("]", 1)[-1].strip().lower()
        exact = [i for i in candidates if messages[i].content.strip().lower() in evidence
                 or evidence in messages[i].content.strip().lower()]
        if exact:
            return exact
        terms = {term for term in re.findall(r"[a-z0-9_-]+", evidence) if len(term) > 3}
        scored = [(len(terms & set(re.findall(r"[a-z0-9_-]+", messages[i].content.lower()))), i)
                  for i in candidates]
        best = max((score for score, _ in scored), default=0)
        return [i for score, i in scored if score == best and score > 0]

    def process_session(self, namespace: str, messages: list[Message], current_date: str | None = None) -> list[str]:
        if not messages:
            return []
        existing = self.episodic.existing_signals(namespace)
        system = self.prompt.replace("<EXISTING_SIGNALS>", json.dumps(existing, ensure_ascii=False))
        system = system.replace("<CURRENT_DATE>", current_date or date.today().isoformat())
        persisted = []
        transcript = []
        message_ids = []
        for message in messages:
            message_id = self.episodic.append_message(namespace, message)
            message_ids.append(message_id)
            transcript.append({"role": message.role, "content": message.content, "timestamp": message.timestamp,
                               "session_id": message.session_id, "message_id": message_id,
                               "channel": message.channel})
        response = self.llm.complete(system=system, messages=[{"role": "user", "content": json.dumps(transcript, ensure_ascii=False)}])
        data = json.loads(response.content)
        for item in data.get("signals", []):
            source_indices = self._source_indices(item["content"], messages)
            source = messages[source_indices[0]] if len(source_indices) == 1 else None
            signal = Signal(
                type=item["type"], content=item["content"], confidence=item["confidence"],
                source_role=source.role if source else "mixed",
                source_time=source.timestamp if source else min(message.timestamp for message in messages),
                session_id=source.session_id if source else messages[0].session_id,
                source_message_id=message_ids[source_indices[0]] if len(source_indices) == 1 else None,
                channel=source.channel if source else (
                    messages[0].channel if len({message.channel for message in messages}) == 1 else "mixed"
                ),
            )
            signal_id = self.episodic.append_signal(namespace, signal)
            if signal_id:
                linked = [message_ids[index] for index in source_indices] or message_ids
                self.episodic.link_signal_messages(namespace, signal_id, linked)
                persisted.append(signal_id)
        return persisted
