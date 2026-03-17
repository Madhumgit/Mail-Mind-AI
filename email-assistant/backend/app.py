from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os

from database        import init_db, insert_email, get_all_emails, get_stats, mark_as_read, delete_email
from gmail_service   import fetch_emails, test_connection
from classifier      import classify_email, train_model, train_bert
from priority_detector import detect_priority
from summarizer      import summarize_email
from scheduler       import start_scheduler, get_next_run, set_processor
from voice_assistant import listen_command, handle_voice_query, speak
from smart_reply     import generate_smart_replies

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
    return response


# ─────────────────────────────────────────────
# Email Processing Pipeline
# ─────────────────────────────────────────────

def process_and_store_emails():
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

        result = insert_email(email_data)
        if result:
            processed += 1

    print(f"[App] Processed and stored {processed} new emails.")
    return processed


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
    category = request.args.get("category", "All")
    priority = request.args.get("priority", "All")
    limit    = int(request.args.get("limit", 100))
    emails   = get_all_emails(category=category, priority=priority, limit=limit)
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
    data = get_stats()
    data["next_scheduled_fetch"] = get_next_run()
    return jsonify(data)


@app.route("/api/connection/test", methods=["GET"])
def connection_test():
    success, message = test_connection()
    return jsonify({"connected": success, "message": message})


# ─────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    email      = os.getenv("EMAIL_ADDRESS", "")
    configured = bool(email and os.getenv("EMAIL_APP_PASSWORD"))
    return jsonify({"email": email, "configured": configured})


@app.route("/api/settings", methods=["POST"])
def save_settings():
    data     = request.get_json()
    email    = data.get("email", "").strip()
    password = data.get("app_password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    env_path    = os.path.join(os.path.dirname(__file__), ".env")
    env_content = f"""# Gmail IMAP Settings
EMAIL_ADDRESS={email}
EMAIL_APP_PASSWORD={password}

# App Settings
FLASK_PORT=5000
SCHEDULER_INTERVAL_MINUTES=30
MAX_EMAILS_PER_FETCH=0
"""
    try:
        with open(env_path, "w") as f:
            f.write(env_content)
        os.environ["EMAIL_ADDRESS"]      = email
        os.environ["EMAIL_APP_PASSWORD"] = password
        return jsonify({"success": True, "message": "Settings saved successfully!"})
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
    """
    Fine-tune DistilBERT on emails in the DB.
    Call after fetching 50+ emails for best accuracy.
    """
    try:
        emails = get_all_emails(limit=500)
        if len(emails) < 10:
            return jsonify({
                "success": False,
                "error": "Need at least 10 emails. Fetch more emails first."
            }), 400

        result = train_bert(emails=emails)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500

        return jsonify({
            "success": True,
            "message": f"DistilBERT trained on {result.get('samples', 0)} emails!",
        })
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
    """Get 3 smart reply suggestions for a specific email by its ID."""
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
    """Get smart replies by passing email content directly."""
    try:
        data    = request.get_json() or {}
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
# Voice Assistant
# ─────────────────────────────────────────────

@app.route("/api/voice/listen", methods=["POST"])
def voice_listen():
    command, error = listen_command(timeout=6)
    if error:
        return jsonify({"success": False, "error": error})
    emails   = get_all_emails(limit=200)
    response = handle_voice_query(command, emails)
    return jsonify({"success": True, "command": command, "response": response})


@app.route("/api/voice/command", methods=["POST"])
def voice_command():
    data    = request.get_json()
    command = data.get("command", "").lower()
    if not command:
        return jsonify({"success": False, "error": "No command provided"})
    emails   = get_all_emails(limit=200)
    response = handle_voice_query(command, emails)
    return jsonify({"success": True, "command": command, "response": response})


@app.route("/api/voice/speak", methods=["POST"])
def voice_speak():
    data = request.get_json()
    text = data.get("text", "")
    if text:
        speak(text)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No text provided"})


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    set_processor(process_and_store_emails)
    interval = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", 30))
    start_scheduler(interval_minutes=interval)
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"[App] Starting Email Assistant API on port {port}")
    app.run(host="0.0.0.0", debug=True, port=port, use_reloader=False)


# ─────────────────────────────────────────────
# Debug Route — check exact email counts
# ─────────────────────────────────────────────

@app.route("/api/debug/counts", methods=["GET"])
def debug_counts():
    """Check how many emails exist in Gmail vs database."""
    try:
        from gmail_service import list_folders
        import imaplib, os

        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_APP_PASSWORD"))

        folder_counts = {}
        folders_to_check = [
            '"[Gmail]/All Mail"',
            "INBOX",
            '"[Gmail]/Spam"',
            '"[Gmail]/Sent Mail"',
        ]

        for f in folders_to_check:
            try:
                status, _ = mail.select(f, readonly=True)
                if status == "OK":
                    _, data = mail.search(None, "ALL")
                    count = len(data[0].split())
                    folder_counts[f] = count
            except:
                folder_counts[f] = "unavailable"

        mail.logout()

        db_count = len(get_all_emails(limit=99999))

        return jsonify({
            "gmail_folders": folder_counts,
            "database_count": db_count,
            "note": "If All Mail count is low, your Gmail account may have few emails"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500