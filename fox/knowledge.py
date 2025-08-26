import sqlite3
from pathlib import Path
from contextlib import closing
import time

DB_PATH = Path(__file__).resolve().parents[1] / "knowledge.db"

def _open():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    return con

def init_db():
    with closing(_open()) as con, closing(con.cursor()) as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)
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
        con.commit()

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
