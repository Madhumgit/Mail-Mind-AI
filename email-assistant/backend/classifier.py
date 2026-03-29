import os
import joblib
import pandas as pd
import nltk
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import re

nltk.download("stopwords", quiet=True)
nltk.download("punkt", quiet=True)
from nltk.corpus import stopwords

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml_model", "classifier.pkl")
DATA_PATH  = os.path.join(os.path.dirname(__file__), "ml_model", "training_data.csv")
STOP_WORDS = set(stopwords.words("english"))

CATEGORIES     = ["Job", "Internship", "Meeting", "Spam", "Other"]
BERT_MODEL_DIR = os.path.join(os.path.dirname(__file__), "ml_model", "distilbert")

# ── BERT globals — never loaded on startup ────────────────────────────────────
USE_BERT        = False
_bert_tokenizer = None
_bert_model     = None
_bert_encoder   = None

# ── TF-IDF model — lazy loaded on first classify call ─────────────────────────
_model = None


def preprocess_text(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 2]
    return " ".join(tokens)


def train_model():
    print("[ML] Training TF-IDF classifier...")
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    print(f"[ML] Loaded {len(df)} training samples")
    df["clean_text"] = df["text"].apply(preprocess_text)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True
        )),
        ("clf", LogisticRegression(
            max_iter=2000,
            C=5.0,
            solver="lbfgs"
        ))
    ])

    pipeline.fit(df["clean_text"], df["category"])
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"[ML] ✅ TF-IDF model saved → {MODEL_PATH}")
    return pipeline


def get_model():
    """Lazy load TF-IDF model — only on first classify call."""
    global _model
    if _model is None:
        if os.path.exists(MODEL_PATH):
            try:
                print("[ML] Loading saved TF-IDF model...")
                _model = joblib.load(MODEL_PATH)
                print("[ML] ✅ TF-IDF model loaded")
            except Exception as e:
                print(f"[ML] Saved model incompatible ({e}) — retraining...")
                _model = train_model()
        else:
            _model = train_model()
    return _model


def classify_email(subject, body):
    """
    Fast TF-IDF classifier. BERT is disabled for performance.
    Returns (category, confidence).
    """
    try:
        text       = f"{subject} {body}"
        clean      = preprocess_text(text)
        model      = get_model()
        prediction = model.predict([clean])[0]
        proba      = model.predict_proba([clean])[0]
        confidence = round(float(max(proba)) * 100, 1)
        return prediction, confidence
    except Exception as e:
        print(f"[ML] Classification error: {e}")
        return "Other", 0.0


# ── BERT training (only called manually via /api/ai/train) ───────────────────

def _load_bert():
    """Load DistilBERT — only called after training, never on startup."""
    global _bert_tokenizer, _bert_model, _bert_encoder, USE_BERT
    if USE_BERT:
        return True
    try:
        import torch
        import pickle
        from transformers import (
            DistilBertTokenizer,
            DistilBertForSequenceClassification,
        )
        from sklearn.preprocessing import LabelEncoder

        if not os.path.exists(BERT_MODEL_DIR):
            return False

        print("[ML] Loading DistilBERT model...")
        _bert_tokenizer = DistilBertTokenizer.from_pretrained(BERT_MODEL_DIR)
        _bert_model     = DistilBertForSequenceClassification.from_pretrained(BERT_MODEL_DIR)
        _bert_model.eval()

        enc_path = os.path.join(os.path.dirname(__file__), "ml_model", "label_encoder.pkl")
        if os.path.exists(enc_path):
            with open(enc_path, "rb") as f:
                _bert_encoder = pickle.load(f)
        else:
            _bert_encoder = LabelEncoder()
            _bert_encoder.fit(CATEGORIES)

        USE_BERT = True
        print("[ML] ✅ DistilBERT loaded!")
        return True
    except Exception as e:
        print(f"[ML] DistilBERT load error: {e}")
        return False


def train_bert(emails: list = None):
    """Fine-tune DistilBERT — called via POST /api/ai/train only."""
    try:
        import torch
        import pickle
        from transformers import (
            DistilBertTokenizer,
            DistilBertForSequenceClassification,
            Trainer,
            TrainingArguments,
        )
        from sklearn.preprocessing import LabelEncoder
        from torch.utils.data import Dataset

        class EmailDataset(Dataset):
            def __init__(self, encodings, labels):
                self.encodings = encodings
                self.labels    = labels
            def __len__(self):
                return len(self.labels)
            def __getitem__(self, idx):
                item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
                item["labels"] = torch.tensor(self.labels[idx])
                return item

        if emails:
            texts  = [f"Subject: {e.get('subject','')} Body: {(e.get('body','') or '')[:512]}" for e in emails]
            labels = [e.get("category", "Other") for e in emails]
            print(f"[ML] Training DistilBERT on {len(texts)} emails...")
        elif os.path.exists(DATA_PATH):
            df     = pd.read_csv(DATA_PATH)
            texts  = df["text"].tolist()
            labels = df["category"].tolist()
            print(f"[ML] Training DistilBERT on {len(texts)} CSV samples...")
        else:
            return {"error": "No training data found"}

        le      = LabelEncoder()
        le.fit(CATEGORIES)
        encoded = le.transform(labels)

        tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")
        encodings = tokenizer(
            texts, truncation=True, padding=True, max_length=256, return_tensors=None
        )
        dataset = EmailDataset(encodings, encoded.tolist())

        model = DistilBertForSequenceClassification.from_pretrained(
            "distilbert-base-uncased", num_labels=len(CATEGORIES)
        )

        os.makedirs(BERT_MODEL_DIR, exist_ok=True)

        args = TrainingArguments(
            output_dir=BERT_MODEL_DIR,
            num_train_epochs=3,
            per_device_train_batch_size=8,
            warmup_steps=50,
            weight_decay=0.01,
            logging_steps=10,
            save_strategy="epoch",
            no_cuda=True,
            report_to="none",
        )

        Trainer(model=model, args=args, train_dataset=dataset).train()

        model.save_pretrained(BERT_MODEL_DIR)
        tokenizer.save_pretrained(BERT_MODEL_DIR)

        enc_path = os.path.join(os.path.dirname(__file__), "ml_model", "label_encoder.pkl")
        with open(enc_path, "wb") as f:
            pickle.dump(le, f)

        _load_bert()
        print("[ML] ✅ DistilBERT training complete!")
        return {"status": "success", "samples": len(texts)}

    except Exception as e:
        print(f"[ML] BERT training error: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    train_model()
