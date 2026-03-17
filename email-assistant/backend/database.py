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

    # ── Emails table ───────────────────────────────────────────────────────────
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
            user_id TEXT DEFAULT 'default',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── User settings table ────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE DEFAULT 'default',
            email_address TEXT,
            app_password TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


# ── User Settings ──────────────────────────────────────────────────────────────

def save_user_settings(email_address: str, app_password: str, user_id: str = "default"):
    """Save Gmail credentials to database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_settings (user_id, email_address, app_password, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email_address = excluded.email_address,
                app_password  = excluded.app_password,
                updated_at    = excluded.updated_at
        """, (user_id, email_address, app_password, datetime.now().isoformat()))
        conn.commit()
        # Update env for current session
        os.environ["EMAIL_ADDRESS"]      = email_address
        os.environ["EMAIL_APP_PASSWORD"] = app_password
        return True
    except Exception as e:
        print(f"[DB] Save settings error: {e}")
        return False
    finally:
        conn.close()


def get_user_settings(user_id: str = "default"):
    """Get Gmail credentials from database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                "email":      row["email_address"],
                "configured": bool(row["email_address"] and row["app_password"]),
            }
        email = os.getenv("EMAIL_ADDRESS", "")
        return {"email": email, "configured": bool(email and os.getenv("EMAIL_APP_PASSWORD"))}
    except Exception as e:
        print(f"[DB] Get settings error: {e}")
        return {"email": "", "configured": False}
    finally:
        conn.close()


def get_user_credentials(user_id: str = "default"):
    """Get full credentials including password."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT email_address, app_password FROM user_settings WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        if row and row["email_address"] and row["app_password"]:
            return row["email_address"], row["app_password"]
        return os.getenv("EMAIL_ADDRESS", ""), os.getenv("EMAIL_APP_PASSWORD", "")
    except Exception as e:
        print(f"[DB] Get credentials error: {e}")
        return os.getenv("EMAIL_ADDRESS", ""), os.getenv("EMAIL_APP_PASSWORD", "")
    finally:
        conn.close()


# ── Email Operations ───────────────────────────────────────────────────────────

def insert_email(email_data, user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO emails
            (message_id, subject, sender, category, priority, summary, body, timestamp, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email_data.get("message_id"),
            email_data.get("subject"),
            email_data.get("sender"),
            email_data.get("category"),
            email_data.get("priority"),
            email_data.get("summary"),
            email_data.get("body"),
            email_data.get("timestamp"),
            user_id,
        ))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"[DB] Insert error: {e}")
        return None
    finally:
        conn.close()


def get_all_emails(category=None, priority=None, limit=100, user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor()
    query  = "SELECT * FROM emails WHERE user_id = ?"
    params = [user_id]
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


def get_stats(user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM emails WHERE user_id = ?", (user_id,))
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT category, COUNT(*) as count FROM emails WHERE user_id = ? GROUP BY category", (user_id,))
    categories = {row["category"]: row["count"] for row in cursor.fetchall()}
    cursor.execute("SELECT priority, COUNT(*) as count FROM emails WHERE user_id = ? GROUP BY priority", (user_id,))
    priorities  = {row["priority"]: row["count"] for row in cursor.fetchall()}
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