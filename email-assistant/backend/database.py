from supabase import create_client
import os
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase credentials")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ───────────────── USER SETTINGS ─────────────────
# NOTE: Your Supabase user_settings table columns are:
#   id (int8), email_address (text), app_password (text),
#   created_at (timestamp), updated_at (timestamp)
# We use email_address as the unique identifier (user_id = email_address)

def save_user_settings(email, password):
    """
    Save or update credentials using email_address as the unique key.
    Checks if email exists → update, else → insert.
    """
    try:
        email    = email.strip().lower()
        password = password.replace(" ", "").strip()

        # Check if this email already exists
        existing = supabase.table("user_settings") \
            .select("id") \
            .eq("email_address", email) \
            .execute()

        if existing.data:
            # Update existing row
            supabase.table("user_settings") \
                .update({
                    "app_password": password,
                    "updated_at":   datetime.utcnow().isoformat()
                }) \
                .eq("email_address", email) \
                .execute()
        else:
            # Insert new row
            supabase.table("user_settings") \
                .insert({
                    "email_address": email,
                    "app_password":  password,
                    "updated_at":    datetime.utcnow().isoformat()
                }) \
                .execute()

        print(f"[DB] Saved settings for {email}")
        return True
    except Exception as e:
        print("Save error:", e)
        return False


def get_user_settings(user_id):
    """Return settings for a specific user (user_id = email_address)."""
    try:
        if not user_id:
            return {"email": "", "configured": False}

        res = supabase.table("user_settings") \
            .select("*") \
            .eq("email_address", user_id) \
            .execute()

        if res.data:
            row = res.data[0]
            return {
                "email":      row["email_address"],
                "configured": bool(row["email_address"] and row["app_password"])
            }

        return {"email": "", "configured": False}
    except Exception as e:
        print("Get settings error:", e)
        return {"email": "", "configured": False}


def get_user_credentials(user_id):
    """
    Return (email, app_password) for a specific user.
    user_id = email_address.
    """
    try:
        if not user_id:
            return "", ""

        res = supabase.table("user_settings") \
            .select("email_address, app_password") \
            .eq("email_address", user_id) \
            .execute()

        if res.data:
            row = res.data[0]
            return row["email_address"], row["app_password"]

        return "", ""
    except Exception as e:
        print("Credential error:", e)
        return "", ""


def get_all_user_ids():
    """
    Return all registered email addresses.
    Used by the scheduler to process every user's inbox.
    """
    try:
        res = supabase.table("user_settings") \
            .select("email_address") \
            .execute()
        return [row["email_address"] for row in res.data] if res.data else []
    except Exception as e:
        print("Get all users error:", e)
        return []


# ───────────────── EMAILS ─────────────────

def insert_email(email_data, user_id):
    try:
        existing = supabase.table("emails") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("message_id", email_data.get("message_id", "")) \
            .execute()

        if existing.data:
            return None

        data = {
            "message_id": email_data.get("message_id"),
            "subject":    email_data.get("subject"),
            "sender":     email_data.get("sender"),
            "category":   email_data.get("category"),
            "priority":   email_data.get("priority"),
            "summary":    email_data.get("summary"),
            "body":       email_data.get("body"),
            "timestamp":  email_data.get("timestamp"),
            "is_read":    False,
            "user_id":    user_id
        }

        result = supabase.table("emails").insert(data).execute()
        print(f"[DB] Insert result: {result.data}")  # ← ADD THIS
        return result.data
    except Exception as e:
        print(f"[DB] Insert error: {e}")  # ← ADD THIS
        return None

def get_all_emails(category=None, priority=None, limit=100, user_id=None):
    try:
        if not user_id:
            return []

        query = supabase.table("emails").select("*").eq("user_id", user_id)

        if category and category != "All":
            query = query.eq("category", category)

        if priority and priority != "All":
            query = query.eq("priority", priority)

        return query.order("timestamp", desc=True).limit(limit).execute().data or []
    except Exception as e:
        print("Fetch error:", e)
        return []


def get_stats(user_id=None):
    try:
        if not user_id:
            return {"total": 0, "categories": {}, "priorities": {}}

        emails = supabase.table("emails") \
            .select("category, priority") \
            .eq("user_id", user_id).execute().data or []

        total      = len(emails)
        categories = {}
        priorities = {}

        for e in emails:
            cat = e.get("category", "Other")
            pri = e.get("priority", "Low")
            categories[cat] = categories.get(cat, 0) + 1
            priorities[pri] = priorities.get(pri, 0) + 1

        return {"total": total, "categories": categories, "priorities": priorities}
    except Exception as e:
        print("Stats error:", e)
        return {"total": 0, "categories": {}, "priorities": {}}


def mark_as_read(email_id):
    try:
        supabase.table("emails").update({"is_read": True}).eq("id", email_id).execute()
    except Exception as e:
        print("Mark read error:", e)


def delete_email(email_id):
    try:
        supabase.table("emails").delete().eq("id", email_id).execute()
    except Exception as e:
        print("Delete error:", e)


def clear_emails(user_id):
    try:
        if user_id:
            supabase.table("emails").delete().eq("user_id", user_id).execute()
    except Exception as e:
        print("Clear error:", e)


def init_db():
    print("Using Supabase PostgreSQL ✅")