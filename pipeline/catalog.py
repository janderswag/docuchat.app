"""SQLite catalog — durable app state for the local UI (matters, documents, threads).

One responsibility: persistence. All queries are parameterized (no string
interpolation). The DB lives at pipeline/.kb_catalog.db (git-ignored, D-28) and is
overridable via ``db_path`` for tests. Matter slugs are path-safe (validated here so
no caller can inject a path).
"""

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = PIPELINE_DIR / ".kb_catalog.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS matters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    display_name TEXT UNIQUE NOT NULL,
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_slug TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    checksum TEXT,
    size_bytes INTEGER,
    status TEXT NOT NULL,
    reason TEXT,
    updated TEXT NOT NULL,
    FOREIGN KEY (matter_slug) REFERENCES matters(slug)
);
CREATE TABLE IF NOT EXISTS transcript_lines (
    doc_id INTEGER NOT NULL,
    page INTEGER NOT NULL,
    line INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    PRIMARY KEY (doc_id, page, line)
);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_slug TEXT NOT NULL,
    title TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    created TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(db_path=None):
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # Idempotent migrations for pre-existing databases (CREATE TABLE IF NOT EXISTS
    # doesn't alter existing tables). doc_type: 'document' | 'transcript' (T-TRANS/D-70,
    # user-designated at upload — never auto-detected).
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN doc_type TEXT NOT NULL DEFAULT 'document'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already present
    return conn


def slugify(name):
    """Path-safe slug: lowercase, non-alphanumeric -> '-', collapsed, trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


# --- matters -----------------------------------------------------------------

def create_matter(display_name, db_path=None):
    name = (display_name or "").strip()
    if not name:
        raise ValueError("display_name is required")
    slug = slugify(name)
    if not slug:
        raise ValueError("display_name has no usable (alphanumeric) characters")
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO matters (slug, display_name, created) VALUES (?, ?, ?)",
            (slug, name, _now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM matters WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise ValueError(f"matter already exists: {name!r}")
    finally:
        conn.close()


def list_matters(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT m.*, (SELECT COUNT(*) FROM documents d WHERE d.matter_slug = m.slug) "
            "AS doc_count FROM matters m ORDER BY m.display_name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_matter(slug, db_path=None):
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM matters WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_matter(slug, db_path=None):
    """Remove a matter row (catalog only). Callers must remove its documents + chunks
    first; this never touches a vector store or any document file."""
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM matters WHERE slug = ?", (slug,))
        conn.commit()
    finally:
        conn.close()


# --- documents ---------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def add_document(matter_slug, file_path, db_path=None, filename=None, status="parsing",
                 doc_type="document"):
    """Insert a documents row (default status 'parsing'); returns the row dict.
    doc_type: 'document' or 'transcript' (user-designated at upload, D-70)."""
    file_path = Path(file_path)
    name = filename or file_path.name
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO documents (matter_slug, filename, stored_path, checksum, size_bytes, "
            "status, reason, updated, doc_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (matter_slug, name, str(file_path), _sha256(file_path),
             file_path.stat().st_size, status, None, _now(), doc_type),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def save_line_map(doc_id, entries, db_path=None):
    """Replace the transcript line map for a document. ``entries`` =
    [(page, line, char_start, char_end)] with offsets into the CLEAN page text (the
    same text chunks slice — so verified span offsets map straight through, D-70)."""
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM transcript_lines WHERE doc_id = ?", (doc_id,))
        conn.executemany(
            "INSERT INTO transcript_lines (doc_id, page, line, char_start, char_end) "
            "VALUES (?, ?, ?, ?, ?)",
            [(doc_id, p, l, s, e) for p, l, s, e in entries])
        conn.commit()
    finally:
        conn.close()


def line_map_for_page(doc_id, page, db_path=None):
    """Ordered [(line, char_start, char_end)] for one transcript page ([] if none)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT line, char_start, char_end FROM transcript_lines "
            "WHERE doc_id = ? AND page = ? ORDER BY line", (doc_id, page)).fetchall()
        return [(r["line"], r["char_start"], r["char_end"]) for r in rows]
    finally:
        conn.close()


def delete_line_map(doc_id, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM transcript_lines WHERE doc_id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


def get_document(doc_id, db_path=None):
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_documents(matter_slug=None, db_path=None):
    conn = _connect(db_path)
    try:
        if matter_slug:
            rows = conn.execute("SELECT * FROM documents WHERE matter_slug = ? ORDER BY updated DESC",
                                (matter_slug,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM documents ORDER BY updated DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_document(doc_id, status, reason=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE documents SET status = ?, reason = ?, updated = ? WHERE id = ?",
                     (status, reason, _now(), doc_id))
        conn.commit()
    finally:
        conn.close()


def delete_document(doc_id, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
    finally:
        conn.close()


# --- threads / messages (chat history) ---------------------------------------

def create_thread(matter_slug, title, db_path=None):
    conn = _connect(db_path)
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO threads (matter_slug, title, created, updated) VALUES (?, ?, ?, ?)",
            (matter_slug, title[:120], now, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM threads WHERE id = ?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


def add_message(thread_id, role, content, citations_json=None, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO messages (thread_id, role, content, citations_json, created) "
            "VALUES (?, ?, ?, ?, ?)",
            (thread_id, role, content, citations_json, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def touch_thread(thread_id, db_path=None):
    conn = _connect(db_path)
    try:
        conn.execute("UPDATE threads SET updated = ? WHERE id = ?", (_now(), thread_id))
        conn.commit()
    finally:
        conn.close()


def list_threads(db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM threads ORDER BY updated DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_thread_messages(thread_id, db_path=None):
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM messages WHERE thread_id = ? ORDER BY id",
                            (thread_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
