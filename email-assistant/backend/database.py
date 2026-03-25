import os
import psycopg2
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ── Emails table ───────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
            user_id TEXT UNIQUE DEFAULT 'default',
            email_address TEXT,
            app_password TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
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
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET
                email_address = EXCLUDED.email_address,
                app_password  = EXCLUDED.app_password,
                updated_at    = EXCLUDED.updated_at
        """, (user_id, email_address, app_password, datetime.now().isoformat()))
        conn.commit()
        os.environ["EMAIL_ADDRESS"]      = email_address
        os.environ["EMAIL_APP_PASSWORD"] = app_password
        return True
    except Exception as e:
        print(f"[DB] Save settings error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_user_settings(user_id: str = "default"):
    """Get Gmail credentials from database."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
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
        cursor.close()
        conn.close()


def get_user_credentials(user_id: str = "default"):
    """Get full credentials including password."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(
            "SELECT email_address, app_password FROM user_settings WHERE user_id = %s",
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
        cursor.close()
        conn.close()


# ── Email Operations ───────────────────────────────────────────────────────────

def insert_email(email_data, user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO emails
            (message_id, subject, sender, category, priority, summary, body, timestamp, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO NOTHING
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
        return cursor.rowcount
    except Exception as e:
        print(f"[DB] Insert error: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def get_all_emails(category=None, priority=None, limit=100, user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query  = "SELECT * FROM emails WHERE user_id = %s"
    params = [user_id]
    if category and category != "All":
        query += " AND category = %s"
        params.append(category)
    if priority and priority != "All":
        query += " AND priority = %s"
        params.append(priority)
    query += " ORDER BY timestamp DESC LIMIT %s"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]


def get_stats(user_id: str = "default"):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT COUNT(*) as total FROM emails WHERE user_id = %s", (user_id,))
    total = cursor.fetchone()["total"]
    cursor.execute("SELECT category, COUNT(*) as count FROM emails WHERE user_id = %s GROUP BY category", (user_id,))
    categories = {row["category"]: row["count"] for row in cursor.fetchall()}
    cursor.execute("SELECT priority, COUNT(*) as count FROM emails WHERE user_id = %s GROUP BY priority", (user_id,))
    priorities  = {row["priority"]: row["count"] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return {"total": total, "categories": categories, "priorities": priorities}


def mark_as_read(email_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE emails SET is_read = 1 WHERE id = %s", (email_id,))
    conn.commit()
    cursor.close()
    conn.close()


def delete_email(email_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM emails WHERE id = %s", (email_id,))
    conn.commit()
    cursor.close()
    conn.close()


def clear_emails(user_id: str = "default"):
    """Clear all emails for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM emails WHERE user_id = %s", (user_id,))
        conn.commit()
        print(f"[DB] Cleared emails for user: {user_id}")
        return True
    except Exception as e:
        print(f"[DB] Clear emails error: {e}")
        return False
    finally:
        cursor.close()
        conn.close()