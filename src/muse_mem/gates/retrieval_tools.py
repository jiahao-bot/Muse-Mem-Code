"""Read-only tools exposed to the Retrieval Gate."""
from __future__ import annotations

import re

from ..storage import EpisodicMemory, SemanticMemory

class RetrievalTools:
    def __init__(self, namespace: str, semantic: SemanticMemory, episodic: EpisodicMemory):
        self.namespace = namespace
        self.semantic = semantic
        self.episodic = episodic

    def read_memory_topic(self, path: str) -> dict:
        topic = self.semantic.read_topic(self.namespace, path)
        if not topic:
            return {"path": path, "exists": False, "entries": []}
        entries = []
        for entry in topic.entries:
            item = entry.__dict__.copy()
            item["source_signal_ids"] = self.semantic.entry_signal_ids(self.namespace, entry.entry_id)
            entries.append(item)
        return {"path": path, "description": topic.description, "keywords": topic.keywords,
                "entries": entries}

    def search_perception_signals(self, query: str, limit: int = 20) -> list[dict]:
        return self.episodic.search_signals(self.namespace, query, limit)

    def search_raw_messages(self, query: str, limit: int = 20) -> list[dict]:
        return self.episodic.search_messages(self.namespace, query, limit)

    def read_supporting_signals(self, entry_ids: list[str]) -> list[dict]:
        return self.episodic.signals_for_entries(self.namespace, entry_ids)

    def read_supporting_raw_messages(self, signal_ids: list[str]) -> list[dict]:
        return self.episodic.messages_for_signals(self.namespace, signal_ids)

    def bash(self, sql: str) -> list[dict]:
        """Execute one namespace-scoped SELECT over the two episodic evidence tables."""
        statement = sql.strip()
        lowered = statement.lower()
        if not lowered.startswith("select ") or ";" in statement or "--" in statement or "/*" in statement:
            raise ValueError("bash(sql) accepts one read-only SELECT statement")
        forbidden = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|replace)\b", re.I)
        if forbidden.search(statement):
            raise ValueError("bash(sql) rejected a non-read-only operation")
        tables = {name.lower() for name in re.findall(r"\b(?:from|join)\s+([A-Za-z_][A-Za-z0-9_]*)", statement, re.I)}
        allowed = {"muse_perceive_signals", "musa_messages"}
        if not tables or not tables.issubset(allowed):
            raise ValueError("bash(sql) may query only muse_perceive_signals and musa_messages")
        scoped = """WITH
        muse_perceive_signals AS (
          SELECT signal_id,session_id,signal_type AS type,content,confidence,
                 source_role,source_time,source_message_id,channel,
                 (SELECT group_concat(pss.message_id) FROM perception_signal_sources pss
                  WHERE pss.namespace=perception_signals.namespace
                    AND pss.signal_id=perception_signals.signal_id) AS source_message_ids,
                 created_at
          FROM perception_signals WHERE namespace=?
        ),
        musa_messages AS (
          SELECT message_id,session_id,role,content,timestamp,channel,created_at
          FROM raw_messages WHERE namespace=?
        )
        """ + statement
        with self.episodic.db.lock:
            rows = self.episodic.db.connection.execute(scoped, (self.namespace, self.namespace)).fetchall()
            return [dict(row) for row in rows]
