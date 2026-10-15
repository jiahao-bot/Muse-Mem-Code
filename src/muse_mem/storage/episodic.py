"""Append-only Episodic Memory."""
from __future__ import annotations

import hashlib
import uuid
from .database import Database
from ..models import Message, Signal, SIGNAL_TYPES, CONFIDENCE_VALUES

class EpisodicMemory:
    def __init__(self, db: Database):
        self.db = db

    def append_message(self, namespace: str, message: Message) -> str:
        stable_key = "\x1f".join((namespace, message.session_id, message.role, message.timestamp,
                                  message.channel, message.content))
        message_id = message.message_id or hashlib.sha256(stable_key.encode()).hexdigest()[:32]
        with self.db.lock:
            self.db.connection.execute(
                """INSERT OR IGNORE INTO raw_messages
                (namespace,message_id,session_id,role,content,timestamp,channel) VALUES(?,?,?,?,?,?,?)""",
                (namespace, message_id, message.session_id, message.role, message.content,
                 message.timestamp, message.channel),
            )
            self.db.connection.commit()
        return message_id

    def append_signal(self, namespace: str, signal: Signal) -> str | None:
        if signal.type not in SIGNAL_TYPES:
            raise ValueError(f"unsupported signal type: {signal.type}")
        if signal.confidence not in CONFIDENCE_VALUES:
            raise ValueError(f"unsupported confidence: {signal.confidence}")
        signal_id = signal.signal_id or uuid.uuid4().hex
        digest = hashlib.sha256(signal.content.strip().encode()).hexdigest()
        with self.db.lock:
            cursor = self.db.connection.execute(
                """INSERT OR IGNORE INTO perception_signals
                (namespace,signal_id,session_id,signal_type,content,confidence,source_role,source_time,source_message_id,channel,content_hash)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (namespace, signal_id, signal.session_id, signal.type, signal.content,
                 signal.confidence, signal.source_role, signal.source_time,
                 signal.source_message_id, signal.channel, digest),
            )
            self.db.connection.commit()
        return signal_id if cursor.rowcount else None

    def link_signal_messages(self, namespace: str, signal_id: str, message_ids: list[str]) -> None:
        with self.db.lock:
            self.db.connection.executemany(
                "INSERT OR IGNORE INTO perception_signal_sources(namespace,signal_id,message_id) VALUES(?,?,?)",
                [(namespace, signal_id, message_id) for message_id in message_ids],
            )
            self.db.connection.commit()

    def existing_signals(self, namespace: str, session_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM perception_signals WHERE namespace=?"
        args: list[str] = [namespace]
        if session_id:
            sql += " AND session_id=?"
            args.append(session_id)
        sql += " ORDER BY source_time, created_at"
        with self.db.lock:
            return [dict(row) for row in self.db.connection.execute(sql, args)]

    def unprocessed_signals(self, namespace: str) -> list[dict]:
        with self.db.lock:
            rows = self.db.connection.execute(
                "SELECT * FROM perception_signals WHERE namespace=? AND processed=0 ORDER BY source_time, created_at",
                (namespace,),
            ).fetchall()
            return [dict(row) for row in rows]

    def search_signals(self, namespace: str, query: str, limit: int = 20) -> list[dict]:
        terms = [term.lower() for term in query.split() if len(term) > 2]
        rows = self.existing_signals(namespace)
        scored = [(sum(term in row["content"].lower() for term in terms), row) for row in rows]
        return [row for score, row in sorted(scored, key=lambda x: x[0], reverse=True) if score][:limit]

    def signals_for_entries(self, namespace: str, entry_ids: list[str]) -> list[dict]:
        if not entry_ids:
            return []
        placeholders = ",".join("?" for _ in entry_ids)
        sql = f"""SELECT DISTINCT s.* FROM perception_signals s
        JOIN topic_entry_sources p ON p.namespace=s.namespace AND p.signal_id=s.signal_id
        WHERE s.namespace=? AND p.entry_id IN ({placeholders}) ORDER BY s.source_time"""
        with self.db.lock:
            return [dict(row) for row in self.db.connection.execute(sql, [namespace, *entry_ids])]

    def messages_for_signals(self, namespace: str, signal_ids: list[str]) -> list[dict]:
        if not signal_ids:
            return []
        placeholders = ",".join("?" for _ in signal_ids)
        sql = f"""SELECT DISTINCT m.* FROM raw_messages m
        JOIN perception_signal_sources s ON s.namespace=m.namespace AND s.message_id=m.message_id
        WHERE s.namespace=? AND s.signal_id IN ({placeholders}) ORDER BY m.timestamp"""
        with self.db.lock:
            return [dict(row) for row in self.db.connection.execute(sql, [namespace, *signal_ids])]

    def search_messages(self, namespace: str, query: str, limit: int = 20) -> list[dict]:
        terms = [term.lower() for term in query.split() if len(term) > 2]
        with self.db.lock:
            rows = [dict(row) for row in self.db.connection.execute(
                "SELECT * FROM raw_messages WHERE namespace=? ORDER BY timestamp", (namespace,)
            )]
        scored = [(sum(term in row["content"].lower() for term in terms), row) for row in rows]
        return [row for score, row in sorted(scored, key=lambda x: x[0], reverse=True) if score][:limit]
