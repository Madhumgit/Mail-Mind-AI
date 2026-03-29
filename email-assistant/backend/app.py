from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import threading

from database        import (init_db, insert_email, get_all_emails, get_stats,
                              mark_as_read, delete_email, save_user_settings,
                              get_user_settings, get_user_credentials, get_all_user_ids,
                              clear_emails)
from gmail_service   import fetch_emails, test_connection
from classifier      import classify_email, train_model, train_bert
from priority_detector import detect_priority
from summarizer      import summarize_email
from scheduler       import start_scheduler, get_next_run, set_processor
from smart_reply     import generate_smart_replies

load_dotenv()

app = Flask(__name__)

CORS(app, resources={r"/api/*": {
    "origins": ["https://mailmind-agent.vercel.app"],
    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def get_user_id_from_request():
    user_id = (
        request.args.get("user_id") or
        (request.get_json(silent=True) or {}).get("user_id") or
        request.headers.get("X-User-Id")
    )
    return user_id.strip().lower() if user_id else None


# ─────────────────────────────────────────────
# Email Processing Pipeline
# ─────────────────────────────────────────────

def process_emails_for_user(user_id):
    """
    Fetch + classify + store emails for ONE specific user.
    Returns count of newly stored emails.
    """
    email_addr, app_pwd = get_user_credentials(user_id)

    if not email_addr or not app_pwd:
        print(f"[App] No credentials for user: {user_id}")
        return 0

    # Limit emails per fetch to avoid timeout — increase gradually
    max_emails = int(os.getenv("MAX_EMAILS_PER_FETCH", 50)) or None
    print(f"[App] Fetching up to {max_emails} emails for {user_id}...")

    raw_emails = fetch_emails(email_addr, app_pwd, max_emails=max_emails)
    print(f"[App] Got {len(raw_emails)} emails from IMAP")

    processed = 0
    for email_data in raw_emails:
        subject = email_data.get("subject", "")
        body    = email_data.get("body", "")

        category, confidence = classify_email(subject, body)
        priority = detect_priority(subject, body, category)
        summary  = summarize_email(subject, body, category)

        email_data["category"]   = category
        email_data["priority"]   = priority
        email_data["summary"]    = summary
        email_data["confidence"] = confidence

        result = insert_email(email_data, user_id=user_id)
        if result:
            processed += 1

    print(f"[App] User {user_id}: stored {processed} new emails.")
    return processed


def process_all_users():
    """Called by scheduler — processes every registered user."""
    user_ids = get_all_user_ids()
    total    = 0
    for uid in user_ids:
        total += process_emails_for_user(uid)
    print(f"[Scheduler] Done. {total} new emails across {len(user_ids)} users.")
    return total


# ── Startup ───────────────────────────────────────────────────────────────────
init_db()
set_processor(process_all_users)
start_scheduler(interval_minutes=int(os.getenv("SCHEDULER_INTERVAL_MINUTES", 30)))


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

@app.route("/", methods=["GET", "HEAD"])
def root():
    return jsonify({"status": "ok"}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Email Assistant API running"})


# ─────────────────────────────────────────────
# Email Routes
# ─────────────────────────────────────────────

@app.route("/api/emails", methods=["GET"])
def get_emails():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    category = request.args.get("category", "All")
    priority = request.args.get("priority", "All")
    limit    = int(request.args.get("limit", 100))

    emails = get_all_emails(category=category, priority=priority,
                            limit=limit, user_id=user_id)
    return jsonify({"emails": emails, "count": len(emails)})


@app.route("/api/emails/fetch", methods=["POST"])
def fetch_now():
    """
    Runs email fetch in a background thread so the HTTP request
    returns immediately — no more Gunicorn worker timeout.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"success": False, "error": "user_id required"}), 400

    try:
        thread = threading.Thread(
            target=process_emails_for_user,
            args=(user_id,),
            daemon=True
        )
        thread.start()
        return jsonify({
            "success": True,
            "message": "Fetching emails in background. Refresh in 1-2 minutes to see them."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emails/<int:email_id>/read", methods=["PATCH"])
def read_email(email_id):
    mark_as_read(email_id)
    return jsonify({"success": True})


@app.route("/api/emails/<int:email_id>", methods=["DELETE"])
def remove_email(email_id):
    delete_email(email_id)
    return jsonify({"success": True})


# ─────────────────────────────────────────────
# Stats & Connection
# ─────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def stats():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    data = get_stats(user_id=user_id)
    data["next_scheduled_fetch"] = get_next_run()
    return jsonify(data)


@app.route("/api/connection/test", methods=["GET"])
def connection_test():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"connected": False, "message": "user_id required"}), 400

    email_addr, app_pwd = get_user_credentials(user_id)
    if not email_addr:
        return jsonify({"connected": False, "message": "No credentials saved for this user"})

    success, message = test_connection(email_addr, app_pwd)
    return jsonify({"connected": success, "message": message})


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"email": "", "configured": False})
    settings = get_user_settings(user_id)
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data     = request.get_json(force=True, silent=True) or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("app_password", "").strip()

    print(f"[Settings] Saving for: {email}")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    try:
        success = save_user_settings(email, password)

        if success:
            clear_emails(email)
            return jsonify({"success": True, "message": "Settings saved & old emails cleared!"})

        return jsonify({"success": False, "error": "Failed to save settings"}), 500

    except Exception as e:
        print(f"[Settings] ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Current user
# ─────────────────────────────────────────────

@app.route("/api/current-email", methods=["GET"])
def current_email():
    user_id = get_user_id_from_request()
    return jsonify({
        "email":     user_id or "",
        "connected": bool(user_id)
    })


# ─────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────

@app.route("/api/train", methods=["POST"])
def retrain():
    try:
        train_model()
        return jsonify({"success": True, "message": "TF-IDF model retrained successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ai/train", methods=["POST"])
def ai_train():
    try:
        user_id = get_user_id_from_request()
        emails  = get_all_emails(limit=500, user_id=user_id)
        if len(emails) < 10:
            return jsonify({"success": False, "error": "Need at least 10 emails."}), 400
        result = train_bert(emails=emails)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "message": f"DistilBERT trained on {result.get('samples', 0)} emails!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ai/status", methods=["GET"])
def ai_status():
    try:
        from classifier import USE_BERT
        import torch
        return jsonify({
            "classifier":   "DistilBERT" if USE_BERT else "TF-IDF",
            "summarizer":   "Fast Extractive (no AI model)",
            "smart_reply":  "Template + Context-aware",
            "device":       "GPU (CUDA)" if torch.cuda.is_available() else "CPU",
            "bert_trained": USE_BERT,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# Smart Replies
# ─────────────────────────────────────────────

@app.route("/api/emails/<int:email_id>/smart-replies", methods=["GET"])
def smart_replies_by_id(email_id):
    try:
        user_id = get_user_id_from_request()
        emails  = get_all_emails(limit=1000, user_id=user_id)
        em      = next((e for e in emails if e["id"] == email_id), None)
        if not em:
            return jsonify({"success": False, "error": "Email not found"}), 404
        replies = generate_smart_replies(
            subject=em.get("subject", ""), body=em.get("body", ""),
            category=em.get("category", "Other"), sender=em.get("sender", ""),
        )
        return jsonify({"success": True, "replies": replies})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/smart-replies", methods=["POST"])
def smart_replies_direct():
    try:
        data    = request.get_json(force=True, silent=True) or {}
        replies = generate_smart_replies(
            subject=data.get("subject", ""), body=data.get("body", ""),
            category=data.get("category", "Other"), sender=data.get("sender", ""),
        )
        return jsonify({"success": True, "replies": replies})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Debug
# ─────────────────────────────────────────────

@app.route("/api/debug/counts", methods=["GET"])
def debug_counts():
    try:
        import imaplib
        user_id             = get_user_id_from_request()
        email_addr, app_pwd = get_user_credentials(user_id)

        if not email_addr:
            return jsonify({"error": "No credentials for this user"}), 400

        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, app_pwd.replace(" ", "").strip())

        folder_counts = {}
        for f in ['"[Gmail]/All Mail"', "INBOX", '"[Gmail]/Spam"', '"[Gmail]/Sent Mail"']:
            try:
                status, _ = mail.select(f, readonly=True)
                if status == "OK":
                    _, data = mail.search(None, "ALL")
                    folder_counts[f] = len(data[0].split())
            except:
                folder_counts[f] = "unavailable"
        mail.logout()

        db_count = len(get_all_emails(limit=99999, user_id=user_id))
        return jsonify({"gmail_folders": folder_counts, "database_count": db_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# Local dev
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", 5000)))
    print(f"[App] Starting on port {port}")
    app.run(host="0.0.0.0", debug=False, port=port, use_reloader=False)
