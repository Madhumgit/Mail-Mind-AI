import imaplib
import email
import os
import re
from email.header import decode_header
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS      = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
IMAP_SERVER        = "imap.gmail.com"
IMAP_PORT          = 993

# All Gmail folders to fetch from
GMAIL_FOLDERS = [
    '"[Gmail]/All Mail"',   # ← contains EVERYTHING
    "INBOX",
    '"[Gmail]/Sent Mail"',
    '"[Gmail]/Drafts"',
    '"[Gmail]/Spam"',
]


def decode_mime_words(s):
    if not s:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(encoding or "utf-8", errors="replace"))
            except Exception:
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except Exception:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    html = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    soup = BeautifulSoup(html, "html.parser")
                    body = soup.get_text(separator=" ")
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")
                if msg.get_content_type() == "text/html":
                    soup = BeautifulSoup(body, "html.parser")
                    body = soup.get_text(separator=" ")
        except Exception:
            pass

    body = re.sub(r"\s+", " ", body).strip()
    return body[:3000]


def fetch_from_folder(mail, folder, max_emails=None):
    """Fetch emails from a single IMAP folder. Returns list of email dicts."""
    emails = []
    try:
        status, _ = mail.select(folder, readonly=True)
        if status != "OK":
            print(f"[IMAP] Could not open folder: {folder}")
            return []

        _, message_numbers = mail.search(None, "ALL")
        all_ids = message_numbers[0].split()

        if not all_ids:
            print(f"[IMAP] No emails in {folder}")
            return []

        # Newest first
        all_ids = all_ids[::-1]
        ids     = all_ids if not max_emails else all_ids[:max_emails]

        print(f"[IMAP] {folder}: Found {len(all_ids)} emails, fetching {len(ids)}...")

        for num in ids:
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue
                raw_email  = msg_data[0][1]
                msg        = email.message_from_bytes(raw_email)

                subject    = decode_mime_words(msg.get("Subject", "No Subject"))
                sender     = decode_mime_words(msg.get("From", "Unknown"))
                date_str   = msg.get("Date", "")
                message_id = msg.get("Message-ID", f"msg_{num.decode()}_{folder}")
                body       = extract_body(msg)

                try:
                    from email.utils import parsedate_to_datetime
                    timestamp = parsedate_to_datetime(date_str).isoformat()
                except Exception:
                    timestamp = datetime.now().isoformat()

                emails.append({
                    "message_id": message_id.strip(),
                    "subject":    subject,
                    "sender":     sender,
                    "body":       body,
                    "timestamp":  timestamp,
                    "folder":     folder,
                })
            except Exception as e:
                print(f"[IMAP] Error parsing email {num}: {e}")
                continue

    except Exception as e:
        print(f"[IMAP] Error fetching from {folder}: {e}")

    return emails


def fetch_emails(max_emails=None, folder="ALL"):
    """
    Fetch emails from Gmail.
    folder="ALL"  → fetches from [Gmail]/All Mail (recommended — contains everything)
    folder="INBOX" → inbox only
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("[IMAP] Missing credentials in .env file")
        return []

    all_emails   = []
    seen_ids     = set()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

        if folder == "ALL":
            # Try [Gmail]/All Mail first — it has EVERYTHING
            fetched = fetch_from_folder(mail, '"[Gmail]/All Mail"', max_emails)

            if fetched:
                # Deduplicate by message_id
                for em in fetched:
                    mid = em["message_id"]
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        all_emails.append(em)
                print(f"[IMAP] ✅ All Mail: {len(all_emails)} unique emails")
            else:
                # Fallback: fetch from INBOX + Spam individually
                print("[IMAP] All Mail unavailable — fetching individual folders...")
                for f in ["INBOX", '"[Gmail]/Spam"']:
                    folder_emails = fetch_from_folder(mail, f, max_emails)
                    for em in folder_emails:
                        mid = em["message_id"]
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            all_emails.append(em)
                print(f"[IMAP] ✅ Total unique emails: {len(all_emails)}")
        else:
            # Specific folder requested
            all_emails = fetch_from_folder(mail, folder, max_emails)

        mail.logout()
        print(f"[IMAP] Successfully fetched {len(all_emails)} emails total")
        return all_emails

    except imaplib.IMAP4.error as e:
        print(f"[IMAP] Login failed: {e}")
        return []
    except Exception as e:
        print(f"[IMAP] Error: {e}")
        return []


def list_folders():
    """Helper to list all available Gmail IMAP folders."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        _, folders = mail.list()
        mail.logout()
        print("[IMAP] Available folders:")
        for f in folders:
            print(f"  {f.decode()}")
    except Exception as e:
        print(f"[IMAP] Error listing folders: {e}")


def test_connection():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        # Also check how many emails exist
        mail.select('"[Gmail]/All Mail"', readonly=True)
        _, data = mail.search(None, "ALL")
        count = len(data[0].split())
        mail.logout()
        return True, f"Connection successful — {count} emails in All Mail"
    except Exception as e:
        return False, str(e)