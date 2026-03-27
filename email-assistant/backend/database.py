from supabase import create_client
import os
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase credentials")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ───────────────── USER SETTINGS ─────────────────

def save_user_settings(email, password, user_id="default"):
    try:
        data = {
            "user_id": user_id,
            "email_address": email.strip(),
            "app_password": password.replace(" ", "").strip(),  # ← add this
            "updated_at": datetime.utcnow().isoformat()
        }

        supabase.table("user_settings").upsert(data).execute()

        os.environ["EMAIL_ADDRESS"] = email
        os.environ["EMAIL_APP_PASSWORD"] = password

        return True
    except Exception as e:
        print("Save error:", e)
        return False


def get_user_settings(user_id="default"):
    try:
        res = supabase.table("user_settings").select("*").eq("user_id", user_id).execute()

        if res.data:
            row = res.data[0]
            return {
                "email": row["email_address"],
                "configured": bool(row["email_address"] and row["app_password"])
            }

        return {"email": "", "configured": False}
    except Exception as e:
        print("Get settings error:", e)
        return {"email": "", "configured": False}


def get_user_credentials(user_id="default"):
    try:
        res = supabase.table("user_settings").select("*").eq("user_id", user_id).execute()

        if res.data:
            row = res.data[0]
            return row["email_address"], row["app_password"]

        return "", ""
    except Exception as e:
        print("Credential error:", e)
        return "", ""


# ───────────────── EMAILS ─────────────────

def insert_email(email_data, user_id):
    try:
        data = {
            "message_id": email_data.get("message_id"),
            "subject": email_data.get("subject"),
            "sender": email_data.get("sender"),
            "category": email_data.get("category"),
            "priority": email_data.get("priority"),
            "summary": email_data.get("summary"),
            "body": email_data.get("body"),
            "timestamp": email_data.get("timestamp"),
            "user_id": user_id
        }

        return supabase.table("emails").insert(data).execute().data
    except Exception as e:
        print("Insert error:", e)
        return None


def get_all_emails(category=None, priority=None, limit=100, user_id="default"):
    try:
        query = supabase.table("emails").select("*").eq("user_id", user_id)

        if category and category != "All":
            query = query.eq("category", category)

        if priority and priority != "All":
            query = query.eq("priority", priority)

        return query.order("timestamp", desc=True).limit(limit).execute().data
    except Exception as e:
        print("Fetch error:", e)
        return []


def get_stats(user_id="default"):
    try:
        emails = supabase.table("emails").select("*").eq("user_id", user_id).execute().data

        total = len(emails)
        categories = {}
        priorities = {}

        for e in emails:
            categories[e["category"]] = categories.get(e["category"], 0) + 1
            priorities[e["priority"]] = priorities.get(e["priority"], 0) + 1

        return {"total": total, "categories": categories, "priorities": priorities}
    except Exception as e:
        print("Stats error:", e)
        return {"total": 0, "categories": {}, "priorities": {}}


def mark_as_read(email_id):
    supabase.table("emails").update({"is_read": True}).eq("id", email_id).execute()


def delete_email(email_id):
    supabase.table("emails").delete().eq("id", email_id).execute()


def clear_emails(user_id="default"):
    supabase.table("emails").delete().eq("user_id", user_id).execute()


# No init needed for Supabase
def init_db():
    print("Using Supabase PostgreSQL ✅")