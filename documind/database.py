import sqlite3
from datetime import datetime, timezone
from documind.config import settings

def connect():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def initialize_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, path TEXT NOT NULL,
            file_type TEXT NOT NULL, text TEXT NOT NULL, pages INTEGER DEFAULT 1,
            sha256 TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL, text TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
            target TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
        );
        """)

def add_document(name, path, file_type, text, pages, digest, chunks):
    with connect() as c:
        cur = c.execute("INSERT INTO documents(name,path,file_type,text,pages,sha256,created_at) VALUES(?,?,?,?,?,?,?)",
                        (name, str(path), file_type, text, pages, digest, datetime.now(timezone.utc).isoformat()))
        doc_id = cur.lastrowid
        c.executemany("INSERT INTO chunks(document_id,chunk_index,text) VALUES(?,?,?)",
                      [(doc_id, i, chunk) for i, chunk in enumerate(chunks)])
    return doc_id

def list_documents():
    with connect() as c:
        rows = c.execute("SELECT d.*, COUNT(ch.id) AS chunk_count FROM documents d LEFT JOIN chunks ch ON ch.document_id=d.id GROUP BY d.id ORDER BY d.created_at DESC").fetchall()
        return [dict(r) for r in rows]

def get_all_chunks(document_names=None):
    with connect() as c:
        if document_names:
            marks = ",".join("?" for _ in document_names)
            rows = c.execute(f"SELECT ch.*, d.name AS document_name FROM chunks ch JOIN documents d ON ch.document_id=d.id WHERE d.name IN ({marks}) ORDER BY d.id,ch.chunk_index", document_names).fetchall()
        else:
            rows = c.execute("SELECT ch.*, d.name AS document_name FROM chunks ch JOIN documents d ON ch.document_id=d.id ORDER BY d.id,ch.chunk_index").fetchall()
        return [dict(r) for r in rows]

def delete_document(doc_id):
    with connect() as c:
        row = c.execute("SELECT path FROM documents WHERE id=?", (doc_id,)).fetchone()
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    if row:
        from pathlib import Path
        Path(row["path"]).unlink(missing_ok=True)

def record_event(event_type, target, details):
    with connect() as c:
        c.execute("INSERT INTO events(event_type,target,details,created_at) VALUES(?,?,?,?)",
                  (event_type, target, details, datetime.now(timezone.utc).isoformat()))

def get_events(limit=100):
    with connect() as c:
        rows = c.execute("SELECT event_type AS Event,target AS Target,details AS Details,created_at AS Timestamp FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

def get_stats():
    with connect() as c:
        return {
            "documents": c.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "chunks": c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0],
            "queries": c.execute("SELECT COUNT(*) FROM events WHERE event_type='query'").fetchone()[0]
        }
