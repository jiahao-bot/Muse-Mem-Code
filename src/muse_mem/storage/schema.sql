PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_messages (
  namespace TEXT NOT NULL,
  message_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'unknown',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (namespace, message_id)
);

CREATE TABLE IF NOT EXISTS perception_signal_sources (
  namespace TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  PRIMARY KEY (namespace, signal_id, message_id),
  FOREIGN KEY (namespace, signal_id)
    REFERENCES perception_signals(namespace, signal_id),
  FOREIGN KEY (namespace, message_id)
    REFERENCES raw_messages(namespace, message_id)
);

CREATE TABLE IF NOT EXISTS core_memory_sources (
  namespace TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  PRIMARY KEY (namespace, signal_id),
  FOREIGN KEY (namespace, signal_id)
    REFERENCES perception_signals(namespace, signal_id)
);

CREATE TABLE IF NOT EXISTS perception_signals (
  namespace TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  signal_type TEXT NOT NULL,
  content TEXT NOT NULL,
  confidence TEXT NOT NULL,
  source_role TEXT NOT NULL,
  source_time TEXT NOT NULL,
  source_message_id TEXT,
  channel TEXT NOT NULL DEFAULT 'unknown',
  content_hash TEXT NOT NULL,
  processed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (namespace, signal_id),
  UNIQUE (namespace, session_id, content_hash),
  FOREIGN KEY (namespace, source_message_id)
    REFERENCES raw_messages(namespace, message_id)
);

CREATE TABLE IF NOT EXISTS semantic_topics (
  namespace TEXT NOT NULL,
  path TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  keywords_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (namespace, path)
);

CREATE TABLE IF NOT EXISTS topic_entries (
  namespace TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  topic_path TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  category TEXT NOT NULL,
  confidence TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  source_context TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (namespace, entry_id),
  FOREIGN KEY (namespace, topic_path)
    REFERENCES semantic_topics(namespace, path)
);

CREATE TABLE IF NOT EXISTS topic_entry_sources (
  namespace TEXT NOT NULL,
  entry_id TEXT NOT NULL,
  signal_id TEXT NOT NULL,
  PRIMARY KEY (namespace, entry_id, signal_id),
  FOREIGN KEY (namespace, entry_id)
    REFERENCES topic_entries(namespace, entry_id),
  FOREIGN KEY (namespace, signal_id)
    REFERENCES perception_signals(namespace, signal_id)
);

CREATE TABLE IF NOT EXISTS topic_links (
  namespace TEXT NOT NULL,
  source_entry_id TEXT NOT NULL,
  target_entry_id TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT 'related',
  PRIMARY KEY (namespace, source_entry_id, target_entry_id)
);

CREATE TABLE IF NOT EXISTS core_memory (
  namespace TEXT NOT NULL PRIMARY KEY,
  content TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snapshots (
  namespace TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  frozen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (namespace, snapshot_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_unprocessed
  ON perception_signals(namespace, processed, source_time);
CREATE INDEX IF NOT EXISTS idx_entries_topic
  ON topic_entries(namespace, topic_path, status);
