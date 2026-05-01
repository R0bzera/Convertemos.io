import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "etiquetas.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id                 INTEGER PRIMARY KEY CHECK (id = 1),
                total_conversions  INTEGER DEFAULT 0
            )
        """)
        conn.execute("INSERT OR IGNORE INTO stats (id, total_conversions) VALUES (1, 0)")


def get_pix_key() -> str:
    with _get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'pix_key'").fetchone()
        return row["value"] if row else ""


def set_pix_key(key: str):
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('pix_key', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key,)
        )


def get_total_conversions() -> int:
    with _get_conn() as conn:
        row = conn.execute("SELECT total_conversions FROM stats WHERE id = 1").fetchone()
        return row["total_conversions"] if row else 0


def increment_conversions():
    with _get_conn() as conn:
        conn.execute("UPDATE stats SET total_conversions = total_conversions + 1 WHERE id = 1")
