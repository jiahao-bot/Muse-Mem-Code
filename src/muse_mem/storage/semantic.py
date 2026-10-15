"""Semantic Memory: Core, Routing Index, and Topic Entries."""
from __future__ import annotations

import json
from .database import Database
from ..models import Topic, TopicEntry

class SemanticMemory:
    def __init__(self, db: Database):
        self.db = db

    def core(self, namespace: str) -> str:
        with self.db.lock:
            row = self.db.connection.execute(
                "SELECT content FROM core_memory WHERE namespace=?", (namespace,)
            ).fetchone()
        return row[0] if row else ""

    def _update_core(self, namespace: str, content: str) -> None:
        self.db.connection.execute(
            """INSERT INTO core_memory(namespace,content) VALUES(?,?)
            ON CONFLICT(namespace) DO UPDATE SET content=excluded.content,updated_at=CURRENT_TIMESTAMP""",
            (namespace, content),
        )

    def routing_index(self, namespace: str) -> list[dict]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT path,description,keywords_json FROM semantic_topics WHERE namespace=? ORDER BY path",
                (namespace,),
            ).fetchall()
        return [{"path": r[0], "description": r[1], "keywords": json.loads(r[2])} for r in rows]

    def read_topic(self, namespace: str, path: str) -> Topic | None:
        with self.db.lock:
            row = self.db.connection.execute(
                "SELECT description,keywords_json FROM semantic_topics WHERE namespace=? AND path=?",
                (namespace, path),
            ).fetchone()
        if not row:
            return None
        entries = []
        with self.db.lock:
            items = self.db.connection.execute(
                "SELECT * FROM topic_entries WHERE namespace=? AND topic_path=? AND status='active' ORDER BY created_at",
                (namespace, path),
            ).fetchall()
            for item in items:
                links = [x[0] for x in self.db.connection.execute(
                    "SELECT target_entry_id FROM topic_links WHERE namespace=? AND source_entry_id=?",
                    (namespace, item["entry_id"]),
                )]
                entries.append(TopicEntry(
                    entry_id=item["entry_id"], file=path, title=item["title"],
                    content=item["content"], category=item["category"],
                    confidence=item["confidence"], status=item["status"],
                    source_context=item["source_context"], links=links,
                ))
        return Topic(path, row[0], json.loads(row[1]), entries)

    def all_entries(self, namespace: str) -> list[TopicEntry]:
        result = []
        for topic in self.routing_index(namespace):
            loaded = self.read_topic(namespace, topic["path"])
            if loaded:
                result.extend(loaded.entries)
        return result

    def entry_signal_ids(self, namespace: str, entry_id: str) -> list[str]:
        with self.db.lock:
            return [row[0] for row in self.db.connection.execute(
                "SELECT signal_id FROM topic_entry_sources WHERE namespace=? AND entry_id=? ORDER BY signal_id",
                (namespace, entry_id),
            )]
