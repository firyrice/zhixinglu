import sqlite3
import os
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_diagnosis_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            direction TEXT NOT NULL,
            shares INTEGER NOT NULL,
            target_price REAL,
            reason TEXT,
            content TEXT NOT NULL,
            summary TEXT,
            holdings_snapshot TEXT,
            chat_history TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_diagnosis(date: str, stock_code: str, stock_name: str, direction: str,
                   shares: int, target_price: float | None, reason: str | None,
                   content: str, summary: str, holdings_snapshot: str) -> int:
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO diagnosis (date, stock_code, stock_name, direction, shares, target_price, reason, content, summary, holdings_snapshot, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (date, stock_code, stock_name, direction, shares, target_price, reason, content, summary, holdings_snapshot, datetime.now().isoformat())
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def list_diagnoses(limit: int = 50) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, date, stock_code, stock_name, direction, shares, target_price, summary, created_at FROM diagnosis ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_diagnosis(diagnosis_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM diagnosis WHERE id = ?", (diagnosis_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_chat_history(diagnosis_id: int, chat_history_json: str) -> bool:
    conn = _get_conn()
    cursor = conn.execute(
        "UPDATE diagnosis SET chat_history = ? WHERE id = ?",
        (chat_history_json, diagnosis_id)
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated


def delete_diagnosis(diagnosis_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM diagnosis WHERE id = ?", (diagnosis_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
