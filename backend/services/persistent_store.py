"""
persistent_store.py — SQLite-backed persistence (no PostgreSQL needed to run)
All analyses, chat histories, and sessions survive server restarts.
"""
import sqlite3, json, time, os, logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)
DB_PATH = os.environ.get("SQLITE_PATH", "./archguide.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    uid TEXT PRIMARY KEY, email TEXT, display_name TEXT DEFAULT '', photo_url TEXT DEFAULT '',
    created_at REAL NOT NULL, last_seen REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY, uid TEXT, title TEXT DEFAULT 'Analysis',
    input_method TEXT DEFAULT 'questionnaire', recommended TEXT DEFAULT '',
    confidence REAL DEFAULT 0, result_json TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL,
    role TEXT NOT NULL, content TEXT NOT NULL,
    analysis_id TEXT DEFAULT '', source TEXT DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT,
    action TEXT NOT NULL, detail TEXT DEFAULT '', created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_uid ON analyses(uid);
CREATE INDEX IF NOT EXISTS idx_chat_uid ON chat_messages(uid);
"""

@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try: yield conn; conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()

def init_db():
    try:
        with _db() as c: c.executescript(SCHEMA)
        logger.info(f"[Store] SQLite ready at {DB_PATH}")
    except Exception as e:
        logger.error(f"[Store] Init failed: {e}")

def upsert_user(uid: str, email: str = "", display_name: str = "", photo_url: str = ""):
    with _db() as c:
        c.execute("INSERT INTO users(uid,email,display_name,photo_url,created_at,last_seen) VALUES(?,?,?,?,?,?) ON CONFLICT(uid) DO UPDATE SET email=excluded.email,display_name=excluded.display_name,last_seen=excluded.last_seen",
                  (uid, email, display_name, photo_url, time.time(), time.time()))

def save_analysis(analysis_id: str, uid: Optional[str], title: str, input_method: str, recommended: str, confidence: float, result: dict):
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO analyses(id,uid,title,input_method,recommended,confidence,result_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                  (analysis_id, uid, title, input_method, recommended, confidence, json.dumps(result), time.time()))

def get_analysis(analysis_id: str) -> Optional[dict]:
    with _db() as c:
        row = c.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if not row: return None
        d = dict(row); d["result"] = json.loads(d.pop("result_json", "{}")); return d

def get_user_analyses(uid: str, limit: int = 50) -> list[dict]:
    with _db() as c:
        rows = c.execute("SELECT id,title,input_method,recommended,confidence,created_at FROM analyses WHERE uid=? ORDER BY created_at DESC LIMIT ?", (uid, limit)).fetchall()
        return [dict(r) for r in rows]

def add_chat_message(uid: str, role: str, content: str, analysis_id: str = "", source: str = "") -> dict:
    with _db() as c:
        cur = c.execute("INSERT INTO chat_messages(uid,role,content,analysis_id,source,created_at) VALUES(?,?,?,?,?,?)",
                        (uid, role, content, analysis_id, source, time.time()))
        return {"id": cur.lastrowid, "role": role, "content": content, "source": source}

def get_chat_history(uid: str, limit: int = 50) -> list[dict]:
    with _db() as c:
        rows = c.execute("SELECT role,content,source,created_at FROM chat_messages WHERE uid=? ORDER BY created_at ASC LIMIT ?", (uid, limit)).fetchall()
        return [dict(r) for r in rows]

def clear_chat(uid: str):
    with _db() as c: c.execute("DELETE FROM chat_messages WHERE uid=?", (uid,))

def log_activity(uid: Optional[str], action: str, detail: str = ""):
    try:
        with _db() as c: c.execute("INSERT INTO activity_log(uid,action,detail,created_at) VALUES(?,?,?,?)", (uid, action, detail, time.time()))
    except Exception: pass

def get_user_stats(uid: str) -> dict:
    with _db() as c:
        total = c.execute("SELECT COUNT(*) FROM analyses WHERE uid=?", (uid,)).fetchone()[0]
        chats = c.execute("SELECT COUNT(*) FROM chat_messages WHERE uid=? AND role='user'", (uid,)).fetchone()[0]
        arch_rows = c.execute("SELECT recommended, COUNT(*) cnt FROM analyses WHERE uid=? GROUP BY recommended", (uid,)).fetchall()
        return {"total_analyses": total, "chat_messages": chats, "arch_distribution": {r["recommended"]: r["cnt"] for r in arch_rows}}

init_db()
