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

# ── DistilBART (lazy loaded) ───────────────────────────────────────────────────
_bart_pipeline = None
_bart_loaded   = False


def _load_bart():
    """Load DistilBART-CNN once. Falls back silently if not available."""
    global _bart_pipeline, _bart_loaded
    if _bart_loaded:
        return _bart_pipeline is not None
    _bart_loaded = True
    try:
        from transformers import pipeline
        print("[Summarizer] Loading DistilBART model (first time only)...")
        _bart_pipeline = pipeline(
            "summarization",
            model="sshleifer/distilbart-cnn-6-6",
            device=-1,   # CPU
        )
        print("[Summarizer] ✅ DistilBART loaded!")
        return True
    except ImportError:
        print("[Summarizer] transformers not installed — using extractive fallback")
        return False
    except Exception as e:
        print(f"[Summarizer] Could not load DistilBART: {e} — using extractive fallback")
        return False


def _bart_summarize(subject: str, body: str):
    """Run DistilBART inference. Returns summary string or None on failure."""
    try:
        input_text = f"{subject}. {_clean_for_bart(body)}"[:1024]
        if len(input_text) < 80:
            return None
        result  = _bart_pipeline(
            input_text,
            max_length=60,
            min_length=20,
            do_sample=False,
            truncation=True,
        )
        summary = result[0]["summary_text"].strip()
        return summary if len(summary) > 15 else None
    except Exception as e:
        print(f"[Summarizer] DistilBART inference error: {e}")
        return None


def _clean_for_bart(text: str) -> str:
    """Clean body text before sending to DistilBART."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"(From|To|Cc|Subject|Date):.*\n", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500]


# ── Original helper functions (100% unchanged) ────────────────────────────────

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


def _extractive_summarize(subject, body, category):
    """Your original summarization logic — used as fallback."""
    if not body or len(body.strip()) < 30:
        return subject if subject else "No content available."

    if category == "Spam":
        return "Promotional or spam message. No action required."

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


# ── Main function (drop-in replacement — same name & signature) ───────────────

def summarize_email(subject, body, category="Other"):
    """
    Upgraded summarizer — tries DistilBART AI first, falls back to
    your original extractive logic automatically.

    Same function name + signature as before — no changes needed in app.py!
    """
    # Spam — instant return, no AI needed
    if category == "Spam":
        return "Promotional or spam message. No action required."

    # Too short — nothing to summarize
    if not body or len(body.strip()) < 50:
        return subject if subject else "No content available."

    # ── 1. Try DistilBART AI ───────────────────────────────────────────────────
    if _load_bart() and _bart_pipeline is not None:
        ai_summary = _bart_summarize(subject, body)
        if ai_summary:
            print(f"[Summarizer] DistilBART → {ai_summary[:60]}...")
            return ai_summary

    # ── 2. Your original extractive logic as fallback ──────────────────────────
    print("[Summarizer] Using extractive fallback")
    return _extractive_summarize(subject, body, category)