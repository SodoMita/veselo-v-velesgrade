"""
dialogue/build_chat_assets.py – Build data-driven chat assets from NPS Chat.

Reads data/raw/nps_chat.zip (vendored, see data/NOTICE.md), and produces:

  data/speech_act_model.json
      A multinomial naive-Bayes classifier mapping an utterance to one of
      GREETING / FAREWELL / QUESTION / STATEMENT, trained on the corpus's
      hand-annotated dialogue acts. Includes held-out evaluation metrics.

  data/chat_phrases.json
      Small-talk inventory mined from the corpus: greetings, farewells,
      backchannels, and "I don't know" stems — with raw counts.

Honest limits (measured, not assumed):
  - The corpus has NO directive/command class, so commands are NOT learned;
    they remain a heuristic (imperative verb whitelist).
  - IRC chat is mostly ungrammatical; we measure the Link Grammar parse
    rate on a sample and only mine *sentence frames* if the corpus is
    grammatical enough to justify it. (Spoiler: it isn't — see report.)

Run:
    python -m velesgrad_v2.dialogue.build_chat_assets
"""

import json
import os
import random
import re
import zipfile
import xml.etree.ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_ZIP = os.path.join(DATA_DIR, "raw", "nps_chat.zip")

# ── Label mapping ────────────────────────────────────────────────────────
# NPS classes → our SpeechAct vocabulary. System posts are dropped.
LABEL_MAP = {
    "Greet": "GREETING",
    "Bye": "FAREWELL",
    "ynQuestion": "QUESTION",
    "whQuestion": "QUESTION",
    # everything else that is conversational → STATEMENT
    "Statement": "STATEMENT", "Emotion": "STATEMENT", "Accept": "STATEMENT",
    "Reject": "STATEMENT", "Emphasis": "STATEMENT", "Continuer": "STATEMENT",
    "yAnswer": "STATEMENT", "nAnswer": "STATEMENT", "Clarify": "STATEMENT",
    "Other": "STATEMENT",
}


def load_posts():
    """Yield (file_name, text, nps_class) for conversational posts."""
    zf = zipfile.ZipFile(RAW_ZIP)
    names = sorted(n for n in zf.namelist() if n.endswith(".xml"))
    for name in names:
        root = ET.parse(zf.open(name)).getroot()
        for post in root.iter("Post"):
            cls = post.get("class")
            if cls not in LABEL_MAP:
                continue  # drops System and anything unmapped
            text = (post.text or "").strip()
            if not text:
                continue
            yield name, text, cls


def tokenize(text: str):
    """Lowercased word tokens + punctuation features."""
    toks = re.findall(r"[a-z']+", text.lower())
    feats = list(toks)
    if text.rstrip().endswith("?"):
        feats.append("<Q>")
    if text.rstrip().endswith("!"):
        feats.append("<EX>")
    # first and last word carry a lot of act signal in chat
    if toks:
        feats.append("<F>:" + toks[0])
        feats.append("<L>:" + toks[-1])
    return feats


class NaiveBayes:
    """Multinomial NB with Laplace smoothing. Pure Python, tiny artifact."""

    def __init__(self):
        self.classes = []
        self.priors = {}       # class -> log P(c)
        self.counts = {}       # class -> {feature: count}
        self.totals = {}       # class -> total feature count
        self.vocab = set()

    def train(self, samples):
        """samples: list of (features:list[str], label:str)"""
        n = len(samples)
        label_counts = {}
        for feats, label in samples:
            label_counts[label] = label_counts.get(label, 0) + 1
        self.classes = sorted(label_counts)
        for c in self.classes:
            self.priors[c] = __import__("math").log(label_counts[c] / n)
            self.counts[c] = {}
            self.totals[c] = 0
        for feats, label in samples:
            for f in feats:
                self.counts[label][f] = self.counts[label].get(f, 0) + 1
                self.totals[label] += 1
                self.vocab.add(f)

    def predict(self, feats):
        import math
        V = max(1, len(self.vocab))
        best, best_score = None, -1e18
        for c in self.classes:
            score = self.priors[c]
            cc = self.counts[c]
            for f in feats:
                score += math.log((cc.get(f, 0) + 1.0) / (self.totals[c] + V))
            if score > best_score:
                best, best_score = c, score
        return best

    def to_json(self):
        return {
            "classes": self.classes,
            "priors": self.priors,
            "counts": self.counts,
            "totals": self.totals,
        }

    @staticmethod
    def from_json(d):
        m = NaiveBayes()
        m.classes = d["classes"]
        m.priors = d["priors"]
        m.counts = d["counts"]
        m.totals = d["totals"]
        for c in m.classes:
            m.vocab.update(m.counts[c].keys())
        return m


def evaluate(model, samples):
    """Overall + per-class accuracy and a majority-class baseline."""
    from collections import Counter
    correct = 0
    per = Counter()
    per_n = Counter()
    label_n = Counter(l for _, l in samples)
    majority = label_n.most_common(1)[0][0]
    base_correct = 0
    for feats, label in samples:
        pred = model.predict(feats)
        per_n[label] += 1
        if pred == label:
            correct += 1
            per[label] += 1
        if label == majority:
            base_correct += 1
    n = len(samples)
    return {
        "accuracy": round(correct / n, 4),
        "baseline_majority_accuracy": round(base_correct / n, 4),
        "per_class": {c: round(per[c] / per_n[c], 3) for c in per_n},
        "per_class_n": dict(per_n),
    }


_DONTKNOW = re.compile(r"\b(i\s+)?(don'?t|do not)\s+know\b|\bno idea\b|\bnot sure\b", re.I)


def mine_phrases(posts):
    """Mine small-talk inventory. Returns chat_phrases dict."""
    from collections import Counter
    greets = Counter()
    byes = Counter()
    backs = Counter()
    dontknow = Counter()

    def clean(t):
        t = re.sub(r"\s+", " ", t).strip().lower()
        return t

    for _, text, cls in posts:
        t = clean(text)
        if not t or "http" in t or len(t) > 40:
            continue
        if cls == "Greet" and len(t.split()) <= 5:
            greets[t] += 1
        elif cls == "Bye" and len(t.split()) <= 5:
            byes[t] += 1
        elif cls in ("Continuer", "Emphasis", "Emotion") and len(t.split()) <= 3:
            backs[t] += 1
        if _DONTKNOW.search(t) and len(t.split()) <= 8:
            dontknow[t] += 1

    def top(counter, k, min_count=2):
        return [{"text": t, "count": c}
                for t, c in counter.most_common(k) if c >= min_count]

    return {
        "greetings": top(greets, 20),
        "farewells": top(byes, 20, min_count=1),
        "backchannels": top(backs, 15),
        "dont_know": top(dontknow, 12, min_count=1),
    }


def measure_lg_parse_rate(posts, sample_size=300):
    """How grammatical is this corpus? (Justifies whether we mine frames.)"""
    try:
        from .lg_ctypes import is_available, get_dictionary, parse_count
    except ImportError:
        return None
    if not is_available():
        return None
    d = get_dictionary()
    rng = random.Random(13)
    sample = rng.sample(posts, min(sample_size, len(posts)))
    ok = 0
    for _, text, _ in sample:
        if parse_count(text, d) > 0:
            ok += 1
    return round(ok / len(sample), 3)


def main():
    if not os.path.exists(RAW_ZIP):
        raise SystemExit(
            f"Missing {RAW_ZIP}. Fetch it with:\n"
            "  curl -L https://raw.githubusercontent.com/nltk/nltk_data/"
            "gh-pages/packages/corpora/nps_chat.zip -o "
            + RAW_ZIP)

    posts = list(load_posts())

    # Split by source file: train on 12 files, test on 3 (disjoint sessions).
    files = sorted({f for f, _, _ in posts})
    test_files = set(files[-3:])
    train = [(tokenize(t), LABEL_MAP[c]) for f, t, c in posts if f not in test_files]
    test = [(tokenize(t), LABEL_MAP[c]) for f, t, c in posts if f in test_files]

    model = NaiveBayes()
    model.train(train)
    metrics = evaluate(model, test)

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(os.path.join(DATA_DIR, "speech_act_model.json"), "w") as f:
        json.dump({
            "provenance": {
                "corpus": "NPS Chat (nps_chat), NLTK data distribution",
                "labels": LABEL_MAP,
                "train_files": len(files) - 3,
                "test_files": 3,
                "train_n": len(train),
                "test_n": len(test),
                "note": "No COMMAND class exists in this corpus; "
                        "commands remain heuristic.",
            },
            "metrics": metrics,
            "model": model.to_json(),
        }, f, indent=1)

    phrases = mine_phrases(posts)
    lg_rate = measure_lg_parse_rate(posts)
    with open(os.path.join(DATA_DIR, "chat_phrases.json"), "w") as f:
        json.dump({
            "provenance": {
                "corpus": "NPS Chat (nps_chat)",
                "lg_parse_rate_sample": lg_rate,
                "frame_mining": "skipped" if (lg_rate is None or lg_rate < 0.5)
                                else "eligible",
            },
            "phrases": phrases,
        }, f, indent=1)

    # ── Compact report ───────────────────────────────────────────────────
    vocab_k = len(model.vocab)
    print(f"train={len(train)} test={len(test)} vocab={vocab_k}")
    print(f"accuracy={metrics['accuracy']} "
          f"(majority baseline {metrics['baseline_majority_accuracy']})")
    print("per-class:", metrics["per_class"])
    print(f"LG parse rate on NPS sample: {lg_rate} -> "
          f"frame mining {'skipped' if (lg_rate or 0) < 0.5 else 'eligible'}")
    for k in ("greetings", "farewells", "backchannels", "dont_know"):
        top = phrases[k][:5]
        print(f"{k} ({len(phrases[k])}):", [x['text'] for x in top])


if __name__ == "__main__":
    main()
