"""Governance Gate agent loop and case-level finalization."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from ..llm import LLM
from ..storage import Database, EpisodicMemory, SemanticMemory
from .governance_tools import GovernanceTools

GOVERNANCE_TOOL_SCHEMA = [
    {"type": "function", "function": {"name": "read_file", "description": "Read an existing user/*.md topic", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "add_file", "description": "Create a semantic topic shell", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Refresh Routing Index metadata", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "description": {"type": "string"}, "keywords": {"type": "array", "items": {"type": "string"}}}, "required": ["path", "description", "keywords"]}}},
    {"type": "function", "function": {"name": "memory_entry", "description": "Add, update, archive, link, or unlink Topic Entries", "parameters": {"type": "object", "properties": {"action": {"enum": ["add", "update", "delete", "link", "unlink"]}, "file": {"type": "string"}, "entry_id": {"type": "string"}, "target_id": {"type": "string"}, "title": {"type": "string"}, "content": {"type": "string"}, "category": {"enum": ["identity", "preference", "relationship", "goal", "context", "insight"]}, "confidence": {"enum": ["confirmed", "inferred", "once", "conflict"]}, "source_context": {"type": "string"}, "links": {"type": "array", "items": {"type": "string"}}}, "required": ["action", "file", "entry_id"]}}},
]

class GovernanceGate:
    def __init__(self, llm: LLM, db: Database, episodic: EpisodicMemory,
                 semantic: SemanticMemory, prompt_path: str, max_rounds: int = 20,
                 batch_size: int = 50):
        self.llm, self.db, self.episodic, self.semantic = llm, db, episodic, semantic
        self.prompt = Path(prompt_path).read_text(encoding="utf-8")
        self.max_rounds = max_rounds
        self.batch_size = max(1, batch_size)

    def finalize(self, namespace: str) -> str | None:
        signals = self.episodic.unprocessed_signals(namespace)
        if not signals:
            return None
        with self.db.transaction():
            for start in range(0, len(signals), self.batch_size):
                batch = signals[start:start + self.batch_size]
                system = self.prompt.replace("<OWNER_MEMORY>", self.semantic.core(namespace))
                system = system.replace("<USER_MEMORY_INDEX>", json.dumps(
                    self.semantic.routing_index(namespace), ensure_ascii=False))
                messages = [{"role": "user", "content": json.dumps(
                    {"perception_signals": batch}, ensure_ascii=False)}]
                tools = GovernanceTools(self.db, self.semantic, namespace, batch)
                for _ in range(self.max_rounds):
                    response = self.llm.complete(system=system, messages=messages,
                                                 tools=GOVERNANCE_TOOL_SCHEMA)
                    if not response.tool_calls:
                        break
                    if response.assistant_message:
                        messages.append(response.assistant_message)
                    for call in response.tool_calls:
                        function = getattr(tools, call.name)
                        result = function(**call.arguments)
                        if call.call_id:
                            messages.append({"role": "tool", "tool_call_id": call.call_id,
                                             "name": call.name,
                                             "content": json.dumps(result, ensure_ascii=False)})
                        else:
                            messages.append({"role": "assistant", "content": json.dumps(
                                {"name": call.name, "arguments": call.arguments, "result": result},
                                ensure_ascii=False)})
                else:
                    raise RuntimeError("governance round limit reached")
            ids = [row["signal_id"] for row in signals]
            covered = {row[0] for row in self.db.connection.execute(
                "SELECT DISTINCT signal_id FROM topic_entry_sources WHERE namespace=?",
                (namespace,),
            )}
            covered.update(row[0] for row in self.db.connection.execute(
                "SELECT signal_id FROM core_memory_sources WHERE namespace=?",
                (namespace,),
            ))
            missing = [signal_id for signal_id in ids if signal_id not in covered]
            if missing:
                raise RuntimeError(f"governance left unrepresented signals: {missing}")
            self.db.connection.executemany(
                "UPDATE perception_signals SET processed=1 WHERE namespace=? AND signal_id=?",
                [(namespace, signal_id) for signal_id in ids],
            )
            snapshot_id = uuid.uuid4().hex
            self.db.connection.execute(
                "INSERT INTO snapshots(namespace,snapshot_id,metadata_json) VALUES(?,?,?)",
                (namespace, snapshot_id, json.dumps({"processed_signal_ids": ids})),
            )
        return snapshot_id
