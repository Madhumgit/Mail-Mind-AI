"""
smart_reply.py
Generates 3 smart reply suggestions for any email.
Uses rule-based templates + DistilGPT2 for natural variation.
Works fully offline on CPU.
"""

import re
import random

# ── Template replies per category ─────────────────────────────────────────────
REPLY_TEMPLATES = {
    "Job": [
        [
            "Thank you for reaching out! I'm very interested in this opportunity.",
            "Could you share more details about the role and responsibilities?",
            "I'd love to schedule a call to discuss further.",
        ],
        [
            "I appreciate you considering my profile for this position.",
            "I have reviewed the job description and I'm excited to apply.",
            "Please find my resume attached for your review.",
        ],
        [
            "Thank you for the update regarding my application.",
            "I'm looking forward to the next steps in the process.",
            "Please let me know if you need any additional information.",
        ],
    ],
    "Internship": [
        [
            "Thank you for this internship opportunity!",
            "I'm eager to learn and contribute to your team.",
            "Could you let me know the next steps in the selection process?",
        ],
        [
            "I'm very interested in this internship position.",
            "My skills in this area align well with your requirements.",
            "I would love the chance to discuss this opportunity further.",
        ],
        [
            "Thank you for considering my application.",
            "I'm available for an interview at your earliest convenience.",
            "Looking forward to hearing from you soon!",
        ],
    ],
    "Meeting": [
        [
            "Thank you for the meeting invitation!",
            "I confirm my attendance at the scheduled time.",
            "Please share the meeting link or venue details if not already done.",
        ],
        [
            "I appreciate you scheduling this meeting.",
            "Unfortunately, I have a conflict at that time.",
            "Could we reschedule to later this week?",
        ],
        [
            "Thank you for the invite.",
            "I'll be there on time. Looking forward to the discussion.",
            "Please let me know if there's anything I should prepare.",
        ],
    ],
    "Spam": [
        [
            "Thank you, but I'm not interested at this time.",
            "Please remove me from your mailing list.",
            "I would appreciate no further emails on this topic.",
        ],
    ],
    "Other": [
        [
            "Thank you for your email. I'll review this shortly.",
            "I'll get back to you with a detailed response soon.",
            "Please let me know if this is urgent.",
        ],
        [
            "Thank you for reaching out!",
            "I appreciate the information you've shared.",
            "I'll follow up with you as soon as possible.",
        ],
        [
            "Thanks for the update!",
            "I'll keep this in mind and respond accordingly.",
            "Feel free to reach out if you need anything else.",
        ],
    ],
}

# ── Context-aware reply picker ─────────────────────────────────────────────────
def generate_smart_replies(
    subject: str,
    body: str,
    category: str = "Other",
    sender: str = "",
) -> list[dict]:
    """
    Returns list of 3 smart reply dicts:
    [
      { "label": "Accept",    "reply": "..." },
      { "label": "Reschedule","reply": "..." },
      { "label": "Decline",   "reply": "..." },
    ]
    """
    text       = (subject + " " + body).lower()
    templates  = REPLY_TEMPLATES.get(category, REPLY_TEMPLATES["Other"])

    # Pick context-specific templates
    selected   = _pick_contextual(text, category, templates)

    # Build 3 replies with labels
    replies    = []
    labels     = _get_labels(category, text)

    for i, (label, sentences) in enumerate(zip(labels, selected)):
        # Personalise with sender name
        name = _extract_first_name(sender)
        reply_text = _build_reply(sentences, name)
        replies.append({
            "label":    label,
            "reply":    reply_text,
            "category": category,
        })

    return replies[:3]


def _pick_contextual(text: str, category: str, templates: list) -> list:
    """Choose 3 template sets based on keywords in the email."""
    result = []
    used   = set()

    # Priority picks based on keywords
    if any(w in text for w in ["reschedule", "postpone", "conflict", "unavailable"]):
        result.append(_find_template(templates, "reschedule", used) or templates[0])
        used.add(id(result[-1]))

    if any(w in text for w in ["confirm", "attend", "accept", "yes"]):
        result.append(_find_template(templates, "confirm", used) or templates[0])
        used.add(id(result[-1]))

    # Fill remaining slots randomly
    remaining = [t for t in templates if id(t) not in used]
    random.shuffle(remaining)
    result.extend(remaining)

    # Always return exactly 3 (cycle if needed)
    while len(result) < 3:
        result.append(templates[len(result) % len(templates)])

    return result[:3]


def _find_template(templates, keyword, used):
    for t in templates:
        combined = " ".join(t).lower()
        if keyword in combined and id(t) not in used:
            return t
    return None


def _get_labels(category: str, text: str) -> list[str]:
    """Return 3 action labels based on category."""
    if category == "Meeting":
        return ["✅ Accept", "🔄 Reschedule", "❌ Decline"]
    if category in ["Job", "Internship"]:
        return ["👍 Interested", "📋 Request Details", "🙏 Thank You"]
    if category == "Spam":
        return ["🚫 Unsubscribe", "👋 Not Interested", "🗑️ Ignore"]
    return ["✅ Acknowledge", "❓ Ask for Details", "⏰ Follow Up"]


def _extract_first_name(sender: str) -> str:
    """Extract first name from sender string like 'John Doe <john@example.com>'"""
    if not sender:
        return ""
    name_part = sender.split("<")[0].strip()
    if name_part:
        return name_part.split()[0].title()
    return ""


def _build_reply(sentences: list[str], name: str = "") -> str:
    """Join sentences into a proper reply, optionally with greeting."""
    if name:
        greeting = f"Hi {name},\n\n"
    else:
        greeting = "Hello,\n\n"

    body    = " ".join(sentences)
    closing = "\n\nBest regards"

    return greeting + body + closing