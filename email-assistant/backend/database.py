import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "emails.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE,
            subject TEXT,
            sender TEXT,
            category TEXT,
            priority TEXT,
            summary TEXT,
            body TEXT,
            timestamp TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


def insert_email(email_data):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO emails 
            (message_id, subject, sender, category, priority, summary, body, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email_data.get("message_id"),
            email_data.get("subject"),
            email_data.get("sender"),
            email_data.get("category"),
            email_data.get("priority"),
            email_data.get("summary"),
            email_data.get("body"),
            email_data.get("timestamp"),
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[DB] Insert error: {e}")
        return None
    finally:
        conn.close()


def get_all_emails(category=None, priority=None, limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM emails WHERE 1=1"
    params = []
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if priority and priority != "All":
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM emails")
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT category, COUNT(*) as count FROM emails GROUP BY category")
    categories = {row["category"]: row["count"] for row in cursor.fetchall()}
    cursor.execute("SELECT priority, COUNT(*) as count FROM emails GROUP BY priority")
    priorities = {row["priority"]: row["count"] for row in cursor.fetchall()}
    conn.close()
    return {"total": total, "categories": categories, "priorities": priorities}


def mark_as_read(email_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE emails SET is_read = 1 WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()


def delete_email(email_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()