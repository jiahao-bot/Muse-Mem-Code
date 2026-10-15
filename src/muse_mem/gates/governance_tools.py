"""Executable Governance tool contract."""
from __future__ import annotations

import json
import re
from ..models import ENTRY_CATEGORIES
from ..storage import Database, SemanticMemory

class GovernanceTools:
    ACTIONS = {"add", "update", "delete", "link", "unlink"}

    def __init__(self, db: Database, semantic: SemanticMemory, namespace: str,
                 signals: list[dict] | None = None):
        self.db = db
        self.semantic = semantic
        self.namespace = namespace
        self.read_paths: set[str] = set()
        self.changed_paths: set[str] = set()
        self.signals = signals or []

    def _source_signal_ids(self, content: str, source_context: str) -> list[str]:
        explicit = set(re.findall(r"signal_id=([A-Za-z0-9_-]+)", source_context))
        if explicit:
            return [signal["signal_id"] for signal in self.signals if signal["signal_id"] in explicit]
        sessions = set(re.findall(r"(?:session_context|session_id)=([^;\], ]+)", source_context))
        candidates = [signal for signal in self.signals if not sessions or signal["session_id"] in sessions]
        normalized = content.lower()
        exact = [signal["signal_id"] for signal in candidates
                 if signal["content"].lower() in normalized or normalized in signal["content"].lower()]
        terms = {term for term in re.findall(r"[a-z0-9_-]+", normalized) if len(term) > 3}
        scored = []
        for signal in candidates:
            signal_terms = {term for term in re.findall(r"[a-z0-9_-]+", signal["content"].lower()) if len(term) > 3}
            overlap = len(terms & signal_terms)
            coverage = overlap / max(1, min(len(terms), len(signal_terms)))
            scored.append((overlap, coverage, signal))
        supported = [signal["signal_id"] for overlap, coverage, signal in scored
                     if overlap >= 2 and coverage >= 0.25]
        combined = list(dict.fromkeys([*exact, *supported]))
        if combined:
            return combined
        best = max((overlap for overlap, _, _ in scored), default=0)
        return [signal["signal_id"] for overlap, _, signal in scored if overlap == best and overlap > 0]

    def read_file(self, path: str) -> dict:
        self.read_paths.add(path)
        topic = self.semantic.read_topic(self.namespace, path)
        if not topic:
            return {"path": path, "exists": False}
        return {"path": path, "description": topic.description, "keywords": topic.keywords,
                "entries": [entry.__dict__ for entry in topic.entries]}

    def add_file(self, path: str, content: str = "") -> dict:
        self.db.connection.execute(
            "INSERT OR IGNORE INTO semantic_topics(namespace,path,description,keywords_json) VALUES(?,?,?,?)",
            (self.namespace, path, content, "[]"),
        )
        self.changed_paths.add(path)
        return {"ok": True, "path": path}

    def edit_file(self, path: str, description: str, keywords: list[str]) -> dict:
        self.db.connection.execute(
            "UPDATE semantic_topics SET description=?,keywords_json=?,updated_at=CURRENT_TIMESTAMP WHERE namespace=? AND path=?",
            (description, json.dumps(keywords, ensure_ascii=False), self.namespace, path),
        )
        self.changed_paths.add(path)
        return {"ok": True, "path": path}

    def memory_entry(self, *, action: str, file: str, entry_id: str, target_id: str = "",
                     title: str = "", content: str = "", category: str = "context",
                     confidence: str = "confirmed", source_context: str = "",
                     links: list[str] | None = None) -> dict:
        if action not in self.ACTIONS:
            raise ValueError(f"unsupported governance action: {action}")
        if category not in ENTRY_CATEGORIES:
            raise ValueError(f"unsupported entry category: {category}")
        if file == "OWNER.md":
            if action not in {"add", "update"} or category != "identity":
                raise ValueError("OWNER.md accepts only add/update identity entries")
            self.semantic._update_core(self.namespace, content)
            for signal_id in self._source_signal_ids(content, source_context):
                self.db.connection.execute(
                    "INSERT OR IGNORE INTO core_memory_sources(namespace,signal_id) VALUES(?,?)",
                    (self.namespace, signal_id),
                )
            return {"ok": True, "action": action, "component": "Core", "entry_id": entry_id}
        if action in {"add", "update"} and file not in self.read_paths:
            raise RuntimeError(f"topic must be read before mutation: {file}")
        if action == "add":
            self.db.connection.execute(
                """INSERT INTO topic_entries(namespace,entry_id,topic_path,title,content,category,confidence,source_context)
                VALUES(?,?,?,?,?,?,?,?)""",
                (self.namespace, entry_id, file, title, content, category, confidence, source_context),
            )
        elif action == "update":
            self.db.connection.execute(
                """UPDATE topic_entries SET title=?,content=?,category=?,confidence=?,source_context=?,updated_at=CURRENT_TIMESTAMP
                WHERE namespace=? AND entry_id=?""",
                (title, content, category, confidence, source_context, self.namespace, entry_id),
            )
        elif action == "delete":
            self.db.connection.execute(
                "UPDATE topic_entries SET status='archived',updated_at=CURRENT_TIMESTAMP WHERE namespace=? AND entry_id=?",
                (self.namespace, entry_id),
            )
        elif action == "link":
            self.db.connection.execute(
                "INSERT OR IGNORE INTO topic_links(namespace,source_entry_id,target_entry_id) VALUES(?,?,?)",
                (self.namespace, entry_id, target_id),
            )
            self.db.connection.execute(
                "INSERT OR IGNORE INTO topic_links(namespace,source_entry_id,target_entry_id) VALUES(?,?,?)",
                (self.namespace, target_id, entry_id),
            )
        elif action == "unlink":
            self.db.connection.execute(
                "DELETE FROM topic_links WHERE namespace=? AND ((source_entry_id=? AND target_entry_id=?) OR (source_entry_id=? AND target_entry_id=?))",
                (self.namespace, entry_id, target_id, target_id, entry_id),
            )
        for signal_id in self._source_signal_ids(content, source_context):
            self.db.connection.execute(
                "INSERT OR IGNORE INTO topic_entry_sources(namespace,entry_id,signal_id) VALUES(?,?,?)",
                (self.namespace, entry_id, signal_id),
            )
        for linked in links or []:
            self.db.connection.execute(
                "INSERT OR IGNORE INTO topic_links(namespace,source_entry_id,target_entry_id) VALUES(?,?,?)",
                (self.namespace, entry_id, linked),
            )
        self.changed_paths.add(file)
        return {"ok": True, "action": action, "entry_id": entry_id}
