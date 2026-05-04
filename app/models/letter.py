import sqlite3
import os
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_letter_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffett_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '致我的合伙人',
            content TEXT NOT NULL,
            summary TEXT,
            portfolio_snapshot TEXT,
            daily_return REAL,
            stock_count INTEGER,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_letter(date: str, content: str, summary: str, portfolio_snapshot: str,
                daily_return: float, stock_count: int) -> int:
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM buffett_letters WHERE date = ?", (date,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE buffett_letters SET content=?, summary=?, portfolio_snapshot=?, daily_return=?, stock_count=?, is_read=0, created_at=? WHERE id=?",
            (content, summary, portfolio_snapshot, daily_return, stock_count, datetime.now().isoformat(), existing["id"])
        )
        conn.commit()
        row_id = existing["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO buffett_letters (date, content, summary, portfolio_snapshot, daily_return, stock_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (date, content, summary, portfolio_snapshot, daily_return, stock_count, datetime.now().isoformat())
        )
        conn.commit()
        row_id = cursor.lastrowid
    conn.close()
    return row_id


def list_letters(limit: int = 50) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, date, title, summary, daily_return, stock_count, is_read, created_at FROM buffett_letters ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_letter(letter_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM buffett_letters WHERE id = ?", (letter_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_letter() -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, date, title, summary, daily_return, stock_count, is_read, created_at FROM buffett_letters ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_read(letter_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("UPDATE buffett_letters SET is_read = 1 WHERE id = ?", (letter_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_letter(letter_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM buffett_letters WHERE id = ?", (letter_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
