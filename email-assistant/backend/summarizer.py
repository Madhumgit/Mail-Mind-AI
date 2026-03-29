import re
import nltk
from collections import Counter

nltk.download("punkt", quiet=True)
nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords

STOP_WORDS = set(stopwords.words("english"))

CATEGORY_TEMPLATES = {
    "Job":        "Job opportunity: {key_info}",
    "Internship": "Internship opportunity: {key_info}",
    "Meeting":    "Meeting: {key_info}",
    "Spam":       "Promotional/spam message detected.",
    "Other":      "{key_info}",
}

IMPORTANT_PATTERNS = [
    r"interview (scheduled|confirmed|invitation|invite).{0,50}",
    r"(offer|position|role).{0,60}",
    r"(meeting|call|sync).{0,50}",
    r"(deadline|due|expires).{0,50}",
    r"(internship|opportunity).{0,60}",
    r"(selected|shortlisted|hired|congratulations).{0,60}",
]


def clean_text(text):
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_key_sentences(text, max_sentences=2):
    text      = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return text[:150]

    word_freq = Counter()
    for sentence in sentences:
        words = sentence.lower().split()
        for w in words:
            if w not in STOP_WORDS and len(w) > 3:
                word_freq[w] += 1

    scored = []
    for s in sentences:
        score = sum(word_freq.get(w.lower(), 0) for w in s.split())
        scored.append((score, s))

    scored.sort(reverse=True)
    top = [s for _, s in scored[:max_sentences]]
    return " ".join(top)


def summarize_email(subject, body, category="Other"):
    """
    Fast extractive summarizer — no heavy AI models.
    Processes each email in milliseconds.
    """
    # Spam — instant return
    if category == "Spam":
        return "Promotional or spam message. No action required."

    # Too short
    if not body or len(body.strip()) < 30:
        return subject if subject else "No content available."

    combined = f"{subject} {body}".lower()
    for pattern in IMPORTANT_PATTERNS:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            key_info = match.group(0).strip().capitalize()
            template = CATEGORY_TEMPLATES.get(category, "{key_info}")
            summary  = template.format(key_info=key_info)
            if len(summary) > 20:
                return summary[:200]

    key_info = extract_key_sentences(body, max_sentences=1)
    template = CATEGORY_TEMPLATES.get(category, "{key_info}")
    summary  = template.format(key_info=key_info)
    return summary[:200]
