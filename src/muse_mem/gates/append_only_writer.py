"""Restricted append-only writer used by the w/o Governance Gate ablation."""
from __future__ import annotations

import hashlib
from ..storage import Database, EpisodicMemory

class AppendOnlyWriter:
    def __init__(self, db: Database, episodic: EpisodicMemory):
        self.db = db
        self.episodic = episodic

    def finalize(self, namespace: str) -> str | None:
        signals = self.episodic.unprocessed_signals(namespace)
        if not signals:
            return None
        path = "user/append-only-signals.md"
        snapshot_id = hashlib.sha256(
            (namespace + "\x1f" + "\x1f".join(row["signal_id"] for row in signals)).encode()
        ).hexdigest()[:32]
        with self.db.transaction():
            self.db.connection.execute(
                "INSERT OR IGNORE INTO semantic_topics(namespace,path,description,keywords_json) VALUES(?,?,?,?)",
                (namespace, path, "Independent append-only Perception Signals", "[]"),
            )
            for signal in signals:
                entry_id = hashlib.sha256((namespace + signal["signal_id"]).encode()).hexdigest()[:32]
                self.db.connection.execute(
                    """INSERT OR IGNORE INTO topic_entries
                    (namespace,entry_id,topic_path,title,content,category,confidence,source_context)
                    VALUES(?,?,?,?,?,?,?,?)""",
                    (namespace, entry_id, path, "Perception Signal", signal["content"],
                     "context", signal["confidence"], signal["session_id"]),
                )
                self.db.connection.execute(
                    "INSERT OR IGNORE INTO topic_entry_sources(namespace,entry_id,signal_id) VALUES(?,?,?)",
                    (namespace, entry_id, signal["signal_id"]),
                )
                self.db.connection.execute(
                    "UPDATE perception_signals SET processed=1 WHERE namespace=? AND signal_id=?",
                    (namespace, signal["signal_id"]),
                )
            self.db.connection.execute(
                "INSERT OR IGNORE INTO snapshots(namespace,snapshot_id,metadata_json) VALUES(?,?,?)",
                (namespace, snapshot_id, '{"ablation":"w/o Governance Gate"}'),
            )
        return snapshot_id
