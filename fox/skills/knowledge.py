import sqlite3
from pathlib import Path
from contextlib import closing
import time

DB_PATH = Path(__file__).resolve().parents[2] / "knowledge.db"

def _open():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    return con

def init_db():
    with closing(_open()) as con, closing(con.cursor()) as cur:
        # Facts (Key/Value)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)
        # Notizen (optional)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                tags TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        # NEU: Training (User-Text → Label)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS training (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text  TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at REAL
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_training_unique
            ON training(text, label)
        """)
        con.commit()

# ---------- Facts ----------
def set_fact(key: str, value: str):
    now = time.time()
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("INSERT OR REPLACE INTO facts(key,value,updated_at) VALUES(?,?,?)",
                    (key, value, now))
        con.commit()

def get_fact(key: str) -> str | None:
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT value FROM facts WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

def search_facts(q: str):
    like = f"%{q}%"
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT key,value FROM facts WHERE key LIKE ? OR value LIKE ?", (like, like))
        return cur.fetchall()

# ---------- Training ----------
def add_training_pair(text: str, label: str) -> None:
    """
    Fügt (text,label) als Trainingsbeispiel hinzu (dedupe via UNIQUE-Index).
    """
    text = (text or "").strip()
    label = (label or "").strip()
    if not text or not label:
        return
    now = time.time()
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("INSERT OR IGNORE INTO training(text,label,created_at) VALUES(?,?,?)",
                    (text, label, now))
        con.commit()

def list_training() -> list[tuple[str, str]]:
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT text, label FROM training ORDER BY id ASC")
        return [(t, l) for (t, l) in cur.fetchall()]

def delete_training(text: str, label: str) -> int:
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("DELETE FROM training WHERE text=? AND label=?", (text, label))
        con.commit()
        return cur.rowcount
