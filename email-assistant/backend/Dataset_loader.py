"""
dataset_loader.py
─────────────────────────────────────────────────────────────────
Downloads the Enron email dataset from Hugging Face,
labels emails into your 5 categories using keyword rules,
saves a balanced training_data.csv ready for TF-IDF + DistilBERT.

Run once:
    python dataset_loader.py
─────────────────────────────────────────────────────────────────
"""

import os
import re
import random
import pandas as pd
from collections import Counter

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "ml_model", "training_data.csv")
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

# ── Category keyword rules ─────────────────────────────────────────────────────
CATEGORY_RULES = {
    "Job": [
        "job opening", "job opportunity", "we are hiring", "position available",
        "software engineer", "data scientist", "developer position", "job offer",
        "full time", "full-time", "invite you for an interview",
        "offer letter", "your application", "selected for interview", "hiring",
        "vacancy", "join our team", "career opportunity", "recruitment",
        "technical interview", "we are looking for", "salary", "compensation",
        "resume", "shortlisted", "candidacy", "job description",
        "apply now", "open position", "job posting", "employment",
        "engineer", "analyst", "developer", "programmer", "architect",
        "manager", "director", "consultant", "specialist", "coordinator",
        "recruiter", "hr team", "human resources", "talent acquisition",
        "work experience", "years of experience", "background in",
        "qualifications", "requirements", "responsibilities",
        "competitive salary", "benefits package", "relocation",
        "immediate joiner", "notice period", "start date",
        "phone screen", "onsite interview", "technical round",
        "we reviewed your", "your profile", "your resume",
        "job fair", "placement", "campus recruitment", "walk in",
        "opening for", "looking for candidates", "seeking experienced",
        "role of", "position of", "we have an opening",
    ],
    "Internship": [
        "internship", "intern position", "summer intern", "winter intern",
        "internship program", "intern opportunity", "paid internship",
        "unpaid internship", "internship offer", "trainee", "apprentice",
        "co-op", "fellowship program", "research intern", "student intern",
        "internship application", "internship interview", "intern role",
        "internship stipend", "academic internship", "graduate program",
        "undergraduate", "final year", "penultimate year", "fresh graduate",
        "entry level", "junior position", "associate position",
        "graduate trainee", "management trainee", "rotational program",
        "industrial training", "on the job training", "ojt",
        "college student", "university student", "campus program",
        "student program", "early career", "new grad",
    ],
    "Meeting": [
        "meeting scheduled", "please join", "zoom call", "conference call",
        "meeting invite", "calendar invite", "standup", "sync call",
        "team meeting", "weekly meeting", "daily scrum", "sprint planning",
        "please confirm attendance", "agenda", "meeting room", "dial-in",
        "video call", "google meet", "microsoft teams invite", "webex",
        "reschedule meeting", "meeting tomorrow", "meeting today",
        "all hands", "town hall", "board meeting", "one on one",
    ],
    "Spam": [
        "click here to claim", "you have won", "free gift", "lucky winner",
        "claim your prize", "limited time offer", "act now", "urgent offer",
        "make money fast", "earn from home", "no experience needed",
        "guaranteed returns", "investment opportunity", "nigerian prince",
        "bank account suspended", "verify your account immediately",
        "congratulations you are selected", "exclusive deal",
        "unsubscribe", "buy now get free", "100% free", "risk free",
        "casino", "lottery", "jackpot", "weight loss", "miracle pill",
        "cheap viagra", "enlarge", "pharmaceutical", "click below to win",
    ],
    "Other": [
        "please find attached", "following up", "as discussed",
        "let me know", "looking forward", "best regards", "kind regards",
        "project update", "status update", "invoice attached",
        "please review", "feedback requested", "quarterly report",
        "team update", "fyi", "for your information", "announcement",
        "newsletter", "company update", "policy update", "reminder",
    ],
}

# ── Text cleaning ──────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\w\s.,!?'-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:1000]


# ── Label email by keyword matching ───────────────────────────────────────────
def label_email(subject: str, body: str) -> str | None:
    text   = (subject + " " + body).lower()
    scores = {cat: 0 for cat in CATEGORY_RULES}

    for cat, keywords in CATEGORY_RULES.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1

    best_cat   = max(scores, key=scores.get)
    best_score = scores[best_cat]

    # Must match at least 1 keyword to be labeled
    if best_score == 0:
        return None

    # If multiple categories tie, skip ambiguous emails
    top_scores = [c for c, s in scores.items() if s == best_score]
    if len(top_scores) > 1 and best_score < 2:
        return None

    return best_cat


# ── Download & process Enron dataset ──────────────────────────────────────────
def load_enron_dataset(max_per_category: int = 2000) -> pd.DataFrame:
    print("[Dataset] Loading Enron email dataset from Hugging Face...")
    print("[Dataset] This may take a few minutes on first download (~500MB)...")

    try:
        from datasets import load_dataset
        # Load Enron dataset
        dataset = load_dataset("SetFit/enron_spam", split="train")
        print(f"[Dataset] ✅ Loaded {len(dataset)} Enron emails")
        return dataset
    except Exception as e:
        print(f"[Dataset] Error loading Enron dataset: {e}")
        raise


def process_enron(dataset, max_per_category: int = 2000) -> pd.DataFrame:
    """Label and balance the Enron dataset into our 5 categories."""
    print("[Dataset] Labeling emails into categories...")

    categorized = {cat: [] for cat in CATEGORY_RULES}
    skipped     = 0

    for item in dataset:
        subject = str(item.get("subject", "") or "")
        text    = str(item.get("text", "") or item.get("body", "") or "")
        label   = item.get("label", 0)

        # Use existing spam label from dataset
        if label == 1:
            clean = clean_text(f"{subject} {text}")
            if clean and len(clean) > 20:
                categorized["Spam"].append(clean)
                continue

        # Label ham emails by keywords
        category = label_email(subject, text)
        if category and category != "Spam":
            clean = clean_text(f"{subject} {text}")
            if clean and len(clean) > 20:
                categorized[category].append(clean)
        else:
            skipped += 1

    # Print raw counts
    print("[Dataset] Raw label counts:")
    for cat, items in categorized.items():
        print(f"  {cat}: {len(items)} emails")

    # Find the smallest category count (excluding zero)
    counts      = {cat: len(items) for cat, items in categorized.items() if len(items) > 0}
    min_count   = min(counts.values())
    target      = min(max_per_category, max(min_count, 300))

    print(f"\n[Dataset] Balancing all categories to ~{target} samples each...")
    rows = []
    for cat, items in categorized.items():
        random.shuffle(items)
        # Oversample minority classes by repeating samples
        if len(items) == 0:
            continue
        if len(items) < target:
            # Repeat samples to reach target
            multiplier = (target // len(items)) + 1
            items      = (items * multiplier)[:target]
            print(f"  ⬆️  {cat}: oversampled to {len(items)} samples")
        else:
            items = items[:target]
            print(f"  ✅ {cat}: {len(items)} samples selected")

        for t in items:
            rows.append({"text": t, "category": cat})

    df = pd.DataFrame(rows)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


# ── Also load supplementary datasets for minority classes ─────────────────────
def load_supplementary_data() -> pd.DataFrame:
    """
    Load additional datasets to boost Job/Internship/Meeting categories
    which may be underrepresented in Enron (corporate emails, not job postings).
    """
    rows = []

    # Try loading email classification dataset from HuggingFace
    try:
        from datasets import load_dataset
        print("\n[Dataset] Loading supplementary email dataset...")
        supp = load_dataset("climatebert/climate_commitments_actions", split="train")
        print(f"[Dataset] Supplementary dataset loaded")
    except Exception:
        pass

    # Add our manually curated samples as a base
    manual_samples = [
        # Job
        ("We are pleased to invite you for an interview for the Software Engineer position.", "Job"),
        ("Your application for the Data Analyst role has been shortlisted.", "Job"),
        ("We have an exciting job opportunity that matches your profile perfectly.", "Job"),
        ("Congratulations! You have been selected for the next round of interviews.", "Job"),
        ("Please find attached the offer letter for the Developer position.", "Job"),
        ("We are hiring a Machine Learning Engineer and your profile is a great fit.", "Job"),
        ("Interview scheduled for Monday at 10 AM for the Backend Developer role.", "Job"),
        ("Your candidacy for the Senior Data Scientist position is under review.", "Job"),
        ("We would like to discuss a full time opportunity in our engineering team.", "Job"),
        ("Technical assessment for the Cloud Engineer position has been scheduled.", "Job"),
        ("We came across your profile and think you'd be great for our team.", "Job"),
        ("Offer letter for the position of Product Manager is attached for review.", "Job"),
        ("Remote job opportunity for Python developers with competitive salary.", "Job"),
        ("Senior Java developer needed for a long term contract project.", "Job"),
        ("Your referral for the Backend Engineer position has been received.", "Job"),
        ("We are conducting campus placements and would like to invite you.", "Job"),
        ("Full time position open for Data Engineers with Spark experience.", "Job"),
        ("Your LinkedIn profile is a great match for our engineering role.", "Job"),
        ("Please complete the coding test for the Software Engineer role by Sunday.", "Job"),
        ("We found your portfolio suitable for a design role at our company.", "Job"),
        # Internship
        ("We are pleased to offer you a summer internship in our Data Science team.", "Internship"),
        ("Applications open for our Software Engineering internship program 2025.", "Internship"),
        ("We would like to invite you for an internship interview at our AI lab.", "Internship"),
        ("Your application for the Web Development internship has been shortlisted.", "Internship"),
        ("We are offering a 3 month internship in our AI division for students.", "Internship"),
        ("Congratulations you have been selected for our summer internship program.", "Internship"),
        ("Please confirm your participation in the 6 month internship program.", "Internship"),
        ("We are delighted to offer you a paid internship as a software trainee.", "Internship"),
        ("Applications for winter internship in cloud computing are now open.", "Internship"),
        ("Your internship application for the product design team is progressing.", "Internship"),
        ("We have shortlisted your profile for a research internship in NLP.", "Internship"),
        ("Intern position available in our cybersecurity team. Apply before deadline.", "Internship"),
        ("Summer internship in full stack development with stipend provided.", "Internship"),
        ("Your application for the UI UX design internship is under review.", "Internship"),
        ("New cohort announced for our machine learning internship program.", "Internship"),
        ("Final year students invited to apply for our 2025 research internship.", "Internship"),
        ("Part time internship available in our marketing analytics team.", "Internship"),
        ("We are accepting applications for a 12 week software internship.", "Internship"),
        ("Internship offer extended for the coming academic semester.", "Internship"),
        ("Competitive internship in finance and data analytics division.", "Internship"),
        # Meeting
        ("You are invited to a team meeting scheduled for tomorrow at 10 AM.", "Meeting"),
        ("The weekly standup meeting is scheduled for Monday at 9 AM.", "Meeting"),
        ("Please confirm your attendance for the quarterly review meeting.", "Meeting"),
        ("You have been invited to a Zoom call with the product team on Wednesday.", "Meeting"),
        ("This is a reminder for the client meeting scheduled for Thursday.", "Meeting"),
        ("The board meeting has been rescheduled to next Tuesday at 10 AM.", "Meeting"),
        ("Join us for a strategy planning session this Monday morning.", "Meeting"),
        ("Your presence is requested at the sprint planning meeting on Friday.", "Meeting"),
        ("Daily scrum has been moved to 8 30 AM starting next Monday.", "Meeting"),
        ("A one on one session with your manager is scheduled for Thursday.", "Meeting"),
        ("Please join the emergency meeting regarding the production outage today.", "Meeting"),
        ("The product roadmap discussion is scheduled for Wednesday afternoon.", "Meeting"),
        ("Monthly one on one with your team lead confirmed for Thursday.", "Meeting"),
        ("Kickoff meeting for the new project is scheduled for Monday.", "Meeting"),
        ("All hands company meeting scheduled for next Monday at 9 AM sharp.", "Meeting"),
        ("Team retrospective and planning session this Friday. Please attend.", "Meeting"),
        ("Interview panel meeting scheduled for tomorrow at 1 PM.", "Meeting"),
        ("Design review meeting moved from 2 PM to 4 PM today.", "Meeting"),
        ("Workshop on agile methodology this Saturday at 10 AM.", "Meeting"),
        ("Vendor evaluation meeting scheduled for this Tuesday morning.", "Meeting"),
        # Spam
        ("Congratulations you have won a free iPhone. Click here to claim now.", "Spam"),
        ("You are selected as a lucky winner. Claim your cash reward immediately.", "Spam"),
        ("Get rich quick with our proven investment strategy. Guaranteed returns.", "Spam"),
        ("Your bank account will be closed. Verify your details immediately.", "Spam"),
        ("Free gift card inside click now to claim your exclusive reward.", "Spam"),
        ("Make money from home easily no experience needed start earning today.", "Spam"),
        ("Nigerian prince needs your help to transfer funds reward of 5 million.", "Spam"),
        ("You have been pre approved for a loan no credit check required.", "Spam"),
        ("Lose 20 pounds in 2 weeks with this miracle pill no diet needed.", "Spam"),
        ("Dear winner you have been selected in our lottery send bank details.", "Spam"),
        ("Limited time offer buy now and get 90 percent off all products.", "Spam"),
        ("Your computer has a virus download our free cleaner software now.", "Spam"),
        ("Exclusive investment opportunity guaranteed 500 percent returns.", "Spam"),
        ("Claim your black friday deal before it expires at midnight tonight.", "Spam"),
        ("Earn money by taking simple surveys online no investment required.", "Spam"),
        ("Your account shows suspicious activity click to verify identity.", "Spam"),
        ("Special discount available for you buy two get three free today.", "Spam"),
        ("You have unused rewards points expiring soon click to redeem.", "Spam"),
        ("Exciting investment opportunity act now before it is too late.", "Spam"),
        ("Congratulations you are our 1 millionth visitor claim prize now.", "Spam"),
        # Other
        ("Please find attached the project report for Q3 review.", "Other"),
        ("Following up on the proposal we discussed last week.", "Other"),
        ("Could you review the attached document and share comments by Friday.", "Other"),
        ("Thank you for your email I will get back to you shortly.", "Other"),
        ("The invoice for last month services is attached for payment.", "Other"),
        ("Please update on the status of the deliverables when available.", "Other"),
        ("Your subscription to our newsletter has been confirmed.", "Other"),
        ("Please find the meeting notes from yesterday. Action items highlighted.", "Other"),
        ("Reminder to submit your expense reports before end of month.", "Other"),
        ("Your order has been shipped and will arrive in 3 to 5 business days.", "Other"),
        ("We have updated our privacy policy please review the changes.", "Other"),
        ("Your password has been successfully reset. Contact support if needed.", "Other"),
        ("The document you requested has been shared via Google Drive.", "Other"),
        ("Please review and sign the attached agreement before Thursday.", "Other"),
        ("Your annual performance review is scheduled for next week.", "Other"),
        ("The budget proposal for Q4 has been approved by the finance team.", "Other"),
        ("Please note the office will remain closed on the upcoming holiday.", "Other"),
        ("Your flight booking confirmation is attached. Have a safe journey.", "Other"),
        ("We are organizing a hackathon next month and invite you to join.", "Other"),
        ("The latest software version is now available for download and update.", "Other"),
    ]

    for text, cat in manual_samples:
        rows.append({"text": text, "category": cat})

    return pd.DataFrame(rows)


# ── Main ───────────────────────────────────────────────────────────────────────
def build_training_data(max_per_category: int = 2000):
    print("=" * 60)
    print("  MailMind Dataset Builder")
    print("  Source: Enron Email Dataset (Hugging Face)")
    print("=" * 60)

    all_dfs = []

    # 1. Load Enron
    try:
        enron_raw = load_enron_dataset()
        enron_df  = process_enron(enron_raw, max_per_category=max_per_category)
        all_dfs.append(enron_df)
        print(f"\n[Dataset] Enron: {len(enron_df)} labeled samples")
    except Exception as e:
        print(f"[Dataset] ⚠️  Could not load Enron: {e}")
        print("[Dataset] Falling back to manual dataset only...")

    # 2. Add supplementary manual samples
    supp_df = load_supplementary_data()
    all_dfs.append(supp_df)
    print(f"[Dataset] Manual samples: {len(supp_df)} samples")

    # 3. Merge all
    if not all_dfs:
        print("[Dataset] ❌ No data loaded!")
        return

    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df = final_df.dropna()
    final_df = final_df[final_df["text"].str.len() > 20]
    final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)

    # 4. Print final stats
    print("\n[Dataset] ✅ Final dataset distribution:")
    counts = Counter(final_df["category"])
    for cat, count in sorted(counts.items()):
        bar = "█" * (count // 50)
        print(f"  {cat:<12} {count:>5} {bar}")
    print(f"\n  TOTAL: {len(final_df)} training samples")

    # 5. Save
    final_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\n[Dataset] 💾 Saved → {OUTPUT_PATH}")
    print("\n[Dataset] Now run: python -c \"from classifier import train_model; train_model()\"")
    print("=" * 60)


if __name__ == "__main__":
    # Install required packages if missing
    try:
        import datasets
    except ImportError:
        print("[Dataset] Installing 'datasets' package...")
        os.system("pip install datasets")
        import datasets

    build_training_data(max_per_category=2000)