-- DocuMind v1 schema (SQLite). Run on every startup; statements are idempotent.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS folders (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  color       TEXT NOT NULL DEFAULT 'amber',
  position    INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_folders_active
  ON folders (deleted_at, position);

CREATE TABLE IF NOT EXISTS docs (
  id            TEXT PRIMARY KEY,
  folder_id     TEXT NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  type          TEXT NOT NULL,                     -- pdf|docx|md|txt|csv|xlsx
  size_bytes    INTEGER NOT NULL,
  sha256        TEXT NOT NULL,
  storage_path  TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending',   -- pending|indexing|ok|error
  error_reason  TEXT,
  outline_json  TEXT,                              -- doc structure cache (sheets/headings/...)
  segment_count INTEGER NOT NULL DEFAULT 0,
  language      TEXT,                              -- zh|ja|en|...
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at    TEXT,
  UNIQUE (folder_id, sha256)
);

CREATE INDEX IF NOT EXISTS idx_docs_folder ON docs (folder_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_docs_status ON docs (status);

CREATE TABLE IF NOT EXISTS chat_sessions (
  id          TEXT PRIMARY KEY,
  title       TEXT,
  scope_mode  TEXT NOT NULL DEFAULT 'all',         -- all|folder
  scope_id    TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id          TEXT PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,                       -- user|assistant
  content     TEXT NOT NULL,
  trace_json  TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_msg_session ON chat_messages (session_id, created_at);

-- FTS5 keyword index. unicode61 with diacritics removal handles CN/JA/EN reasonably;
-- jieba/sudachipy can post-process queries for CJK if accuracy is insufficient later.
CREATE VIRTUAL TABLE IF NOT EXISTS fts_segments USING fts5(
  doc_id UNINDEXED,
  folder_id UNINDEXED,
  locator UNINDEXED,
  content,
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS agent_runs (
  id           TEXT PRIMARY KEY,
  session_id   TEXT,
  trace_id     TEXT NOT NULL,
  status       TEXT NOT NULL,                      -- running|done|error|cancelled
  steps        INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at  TEXT
);
