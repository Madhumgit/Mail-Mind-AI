from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os

from database        import init_db, insert_email, get_all_emails, get_stats, mark_as_read, delete_email, save_user_settings, get_user_settings, get_user_credentials
from gmail_service   import fetch_emails, test_connection
from classifier      import classify_email, train_model, train_bert
from priority_detector import detect_priority
from summarizer      import summarize_email
from scheduler       import start_scheduler, get_next_run, set_processor
from smart_reply     import generate_smart_replies

load_dotenv()

app = Flask(__name__)

# ✅ FIXED CORS — exact origin, no wildcard conflict
CORS(app, resources={r"/api/*": {
    "origins": ["https://mailmind-agent.vercel.app"],
    "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})


# ─────────────────────────────────────────────
# Email Processing Pipeline
# ─────────────────────────────────────────────

def process_and_store_emails():
    email_addr, app_pwd = get_user_credentials()
    if not email_addr or not app_pwd:
        print("[App] No credentials found. Please configure Gmail settings.")
        return 0
    os.environ["EMAIL_ADDRESS"]      = email_addr
    os.environ["EMAIL_APP_PASSWORD"] = app_pwd
    raw_emails = fetch_emails(max_emails=int(os.getenv("MAX_EMAILS_PER_FETCH", 0)) or None)
    processed  = 0
    for email_data in raw_emails:
        subject  = email_data.get("subject", "")
        body     = email_data.get("body", "")

        category, confidence = classify_email(subject, body)
        priority = detect_priority(subject, body, category)
        summary  = summarize_email(subject, body, category)

        email_data["category"]   = category
        email_data["priority"]   = priority
        email_data["summary"]    = summary
        email_data["confidence"] = confidence

        email_addr, _ = get_user_credentials()
        result = insert_email(email_data, user_id=email_addr)
        if result:
            processed += 1

    print(f"[App] Processed and stored {processed} new emails.")
    return processed


# ── Initialize DB + scheduler on startup (works with gunicorn) ────────────────
init_db()
set_processor(process_and_store_emails)
start_scheduler(interval_minutes=int(os.getenv("SCHEDULER_INTERVAL_MINUTES", 30)))


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "Email Assistant API running"})


# ─────────────────────────────────────────────
# Email Routes
# ─────────────────────────────────────────────

@app.route("/api/emails", methods=["GET"])
def get_emails():
    email_addr, _ = get_user_credentials()

    category = request.args.get("category", "All")
    priority = request.args.get("priority", "All")
    limit    = int(request.args.get("limit", 100))

    emails = get_all_emails(
        category=category,
        priority=priority,
        limit=limit,
        user_id=email_addr
    )

    return jsonify({"emails": emails, "count": len(emails)})


@app.route("/api/emails/fetch", methods=["POST"])
def fetch_now():
    try:
        count = process_and_store_emails()
        return jsonify({"success": True, "message": f"Fetched and processed {count} new emails."})
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
    email_addr, _ = get_user_credentials()
    data = get_stats(user_id=email_addr)
    data["next_scheduled_fetch"] = get_next_run()
    return jsonify(data)


@app.route("/api/connection/test", methods=["GET"])
def connection_test():
    email_addr, app_pwd = get_user_credentials()
    if email_addr:
        os.environ["EMAIL_ADDRESS"]      = email_addr
        os.environ["EMAIL_APP_PASSWORD"] = app_pwd
    success, message = test_connection()
    return jsonify({"connected": success, "message": message})


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = get_user_settings()
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data     = request.get_json(force=True, silent=True) or {}
    email    = data.get("email", "").strip()
    password = data.get("app_password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    try:
        success = save_user_settings(email, password)

        if success:
            from database import clear_emails
            clear_emails()
            return jsonify({"success": True, "message": "Settings saved & old emails cleared!"})

        return jsonify({"success": False, "error": "Failed to save settings"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ─────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────

@app.route("/api/train", methods=["POST"])
def retrain():
    """Retrain TF-IDF on training_data.csv."""
    try:
        train_model()
        return jsonify({"success": True, "message": "TF-IDF model retrained successfully."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ai/train", methods=["POST"])
def ai_train():
    """Fine-tune DistilBERT on emails in the DB."""
    try:
        emails = get_all_emails(limit=500)
        if len(emails) < 10:
            return jsonify({"success": False, "error": "Need at least 10 emails. Fetch more emails first."}), 400
        result = train_bert(emails=emails)
        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "message": f"DistilBERT trained on {result.get('samples', 0)} emails!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/ai/status", methods=["GET"])
def ai_status():
    """Check which AI models are active."""
    try:
        from classifier import USE_BERT
        import torch
        return jsonify({
            "classifier":   "DistilBERT" if USE_BERT else "TF-IDF (BERT not trained yet)",
            "summarizer":   "DistilBART (loads on first use)",
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
        emails = get_all_emails(limit=1000)
        email  = next((e for e in emails if e["id"] == email_id), None)
        if not email:
            return jsonify({"success": False, "error": "Email not found"}), 404
        replies = generate_smart_replies(
            subject  = email.get("subject", ""),
            body     = email.get("body", ""),
            category = email.get("category", "Other"),
            sender   = email.get("sender", ""),
        )
        return jsonify({"success": True, "replies": replies})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/smart-replies", methods=["POST"])
def smart_replies_direct():
    try:
        data    = request.get_json(force=True, silent=True) or {}
        replies = generate_smart_replies(
            subject  = data.get("subject", ""),
            body     = data.get("body", ""),
            category = data.get("category", "Other"),
            sender   = data.get("sender", ""),
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
        email_addr, app_pwd = get_user_credentials()
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
        db_count = len(get_all_emails(limit=99999))
        return jsonify({"gmail_folders": folder_counts, "database_count": db_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/current-email", methods=["GET"])
def current_email():
    email_addr, _ = get_user_credentials()
    return jsonify({
        "email": email_addr,
        "connected": bool(email_addr)
    })


# ─────────────────────────────────────────────
# Startup (local dev only)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", 5000)))
    print(f"[App] Starting Email Assistant API on port {port}")
    app.run(host="0.0.0.0", debug=False, port=port, use_reloader=False)