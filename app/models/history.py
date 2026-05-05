import sqlite3
import os
from datetime import datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            stock_name TEXT NOT NULL,
            market TEXT NOT NULL DEFAULT 'A',
            analysis_date TEXT NOT NULL,
            html_content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_report(stock_code: str, stock_name: str, html_content: str, market: str = "A") -> int:
    now = datetime.now()
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO analysis_history (stock_code, stock_name, market, analysis_date, html_content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (stock_code, stock_name, market, now.strftime("%Y-%m-%d %H:%M"), html_content, now.isoformat()),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def list_reports(limit: int = 50) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, stock_code, stock_name, market, analysis_date, created_at FROM analysis_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report(report_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM analysis_history WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_report(report_id: int) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM analysis_history WHERE id = ?", (report_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def get_recent_report(stock_code: str, days: int = 2) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM analysis_history WHERE stock_code = ? AND created_at > datetime('now', ? || ' days') ORDER BY created_at DESC LIMIT 1",
        (stock_code, f"-{days}"),
    ).fetchone()
    conn.close()
    return dict(row) if row else None
