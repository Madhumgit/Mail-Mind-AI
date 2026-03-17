import re

HIGH_KEYWORDS = [
    "urgent", "asap", "immediately", "interview", "offer letter", "deadline",
    "action required", "important", "critical", "emergency", "final round",
    "meeting today", "reminder", "expires", "last chance", "overdue",
    "due today", "respond now", "time sensitive", "mandatory", "confirmed"
]

MEDIUM_KEYWORDS = [
    "schedule", "follow up", "please review", "next steps", "upcoming",
    "soon", "this week", "next week", "application received", "shortlisted",
    "invited", "please confirm", "meeting invite", "attached", "invoice",
    "renewal", "subscription", "document", "report"
]

LOW_KEYWORDS = [
    "newsletter", "update", "announcement", "fyi", "no action required",
    "just wanted to share", "monthly", "weekly", "digest", "recap",
    "summary", "blog", "tips", "insight"
]


def detect_priority(subject, body, category):
    text = f"{subject} {body}".lower()

    # Spam is always low priority
    if category == "Spam":
        return "Low"

    # Count keyword matches
    high_score = sum(1 for kw in HIGH_KEYWORDS if kw in text)
    medium_score = sum(1 for kw in MEDIUM_KEYWORDS if kw in text)
    low_score = sum(1 for kw in LOW_KEYWORDS if kw in text)

    # Category-based boost
    if category == "Meeting":
        high_score += 2
    elif category in ["Job", "Internship"]:
        if any(w in text for w in ["interview", "offer", "selected", "hired"]):
            high_score += 3
        else:
            medium_score += 1

    # Determine priority
    if high_score >= 1:
        return "High"
    elif medium_score >= 1:
        return "Medium"
    else:
        return "Low"