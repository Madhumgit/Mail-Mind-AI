import imaplib
import email
import os
import re
from email.header import decode_header
from datetime import datetime
from bs4 import BeautifulSoup

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT   = 993


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


def fetch_from_folder(mail, folder, max_emails=None, offset=0):
    """
    Fetch emails from a single IMAP folder.
    offset: skip first N emails (for batching)
    max_emails: how many to fetch after offset
    """
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

        # Apply offset
        all_ids = all_ids[offset:]

        # Apply limit
        ids = all_ids if not max_emails else all_ids[:max_emails]

        print(f"[IMAP] {folder}: Total={len(message_numbers[0].split())} offset={offset} fetching={len(ids)}...")

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


def fetch_emails(email_address, app_password, max_emails=None, offset=0, folder="ALL"):
    """
    Fetch emails for a specific user.
    max_emails: how many to fetch (None = all)
    offset: skip first N emails (used for batching)
    """
    if not email_address or not app_password:
        print("[IMAP] Missing credentials")
        return []

    app_password = app_password.replace(" ", "").strip()
    all_emails   = []
    seen_ids     = set()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_address, app_password)
        print(f"[IMAP] Logged in as {email_address}")

        if folder == "ALL":
            fetched = fetch_from_folder(
                mail, '"[Gmail]/All Mail"',
                max_emails=max_emails,
                offset=offset
            )

            if fetched:
                for em in fetched:
                    mid = em["message_id"]
                    if mid not in seen_ids:
                        seen_ids.add(mid)
                        all_emails.append(em)
                print(f"[IMAP] ✅ Fetched {len(all_emails)} unique emails (offset={offset})")
            else:
                # Fallback to INBOX + Spam
                print("[IMAP] All Mail unavailable — fetching individual folders...")
                for f in ["INBOX", '"[Gmail]/Spam"']:
                    folder_emails = fetch_from_folder(
                        mail, f,
                        max_emails=max_emails,
                        offset=offset
                    )
                    for em in folder_emails:
                        mid = em["message_id"]
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            all_emails.append(em)
        else:
            all_emails = fetch_from_folder(
                mail, folder,
                max_emails=max_emails,
                offset=offset
            )

        mail.logout()
        print(f"[IMAP] Done. Fetched {len(all_emails)} emails for {email_address}")
        return all_emails

    except imaplib.IMAP4.error as e:
        print(f"[IMAP] Login failed for {email_address}: {e}")
        return []
    except Exception as e:
        print(f"[IMAP] Error: {e}")
        return []


def get_total_email_count(email_address, app_password):
    """Return total number of emails in All Mail."""
    try:
        app_password = app_password.replace(" ", "").strip()
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_address, app_password)
        mail.select('"[Gmail]/All Mail"', readonly=True)
        _, data = mail.search(None, "ALL")
        count = len(data[0].split())
        mail.logout()
        return count
    except Exception as e:
        print(f"[IMAP] Count error: {e}")
        return 0


def test_connection(email_address, app_password):
    """Test IMAP connection. Returns (success, message)."""
    if not email_address or not app_password:
        return False, "No credentials provided"

    app_password = app_password.replace(" ", "").strip()

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_address, app_password)
        mail.select('"[Gmail]/All Mail"', readonly=True)
        _, data  = mail.search(None, "ALL")
        count    = len(data[0].split())
        mail.logout()
        return True, f"Connection successful — {count} emails in All Mail"
    except Exception as e:
        return False, str(e)
