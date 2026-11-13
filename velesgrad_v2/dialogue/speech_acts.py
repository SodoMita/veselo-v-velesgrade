"""
dialogue/speech_acts.py – Data-driven speech-act classification & small talk.

Loads artifacts built by build_chat_assets.py:
  data/speech_act_model.json – naive Bayes (NPS Chat, 80.5% held-out acc
                               vs 66.8% majority baseline; see metrics inside)
  data/chat_phrases.json     – mined greetings / farewells / backchannels /
                               "I don't know" stems with raw counts

Design decisions (deliberate, documented):
  - COMMAND is NOT learned: the NPS corpus has no directive class.
    Imperative detection stays heuristic (see DialogueManager.recognize_act).
  - Mined phrases pass a *register filter* before use in the fantasy-
    archivist chat: we keep only short, neutral items ("well", "i see",
    "not sure") and reject IRC debris ("hi 10-19-40suser30", "lmao").
    The filter and counts are visible in the artifact.
"""

import json
import os
import re

_DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_MODEL_PATH = os.path.join(_DATA, "speech_act_model.json")
_PHRASES_PATH = os.path.join(_DATA, "chat_phrases.json")

_model = None
_phrases = None
_tried = False


def _load():
    global _model, _phrases, _tried
    if _tried:
        return
    _tried = True
    try:
        with open(_MODEL_PATH) as f:
            blob = json.load(f)
        from .build_chat_assets import NaiveBayes, tokenize
        m = NaiveBayes.from_json(blob["model"])
        _model = (m, tokenize, blob.get("metrics", {}))
    except (OSError, KeyError, ValueError):
        _model = None
    try:
        with open(_PHRASES_PATH) as f:
            _phrases = json.load(f).get("phrases", {})
    except (OSError, ValueError):
        _phrases = None


def available() -> bool:
    """True when trained artifacts exist."""
    _load()
    return _model is not None


def metrics() -> dict:
    _load()
    return _model[2] if _model else {}


def classify(text: str) -> str | None:
    """Predict GREETING / FAREWELL / QUESTION / STATEMENT, or None if no model."""
    _load()
    if _model is None:
        return None
    m, tokenize, _ = _model
    return m.predict(tokenize(text))


# ── Register-filtered small talk ─────────────────────────────────────────

_REGISTER_OK_WORDS = {
    "well", "ah", "oh", "oops", "hmm", "really", "right", "sure",
    "indeed", "i see", "of course", "okay", "ok", "yes", "no",
    "not sure", "no idea", "i don't know", "i dont know", "dont know",
    "don't know", "good", "fine", "nice",
}

_CLEAN = re.compile(r"^[a-z' ]+$")

# Parting/greeting PATTERNS verified present in the NPS corpus
# (counts: "see you" 9, "good night" 4, "i'm off" 3, "gotta go" 2,
#  "good evening" 2, "take care" 1, "im off" 2). Register-filtered:
# IRC shorthand (brb, tc, hb, afk, g2g) is excluded on purpose.
_FAREWELL_PATTERNS = (
    "see you", "see ya", "good night", "goodnight", "gotta go",
    "i'm off", "im off", "take care", "farewell", "goodbye", "bye",
)
_GREETING_PATTERNS = (
    "good evening", "good day", "hello", "hey", "hi", "greetings",
    "morning", "evening",
)


def farewell_pattern(text: str) -> bool:
    t = " " + re.sub(r"\s+", " ", text.lower()).strip(" .!,") + " "
    return any((" " + p) in t for p in _FAREWELL_PATTERNS)


def greeting_pattern(text: str) -> bool:
    t = " " + re.sub(r"\s+", " ", text.lower()).strip(" .!,") + " "
    words = t.split()
    if len(words) > 5:
        return False
    return any((" " + p + " ") in t or t.strip().startswith(p) for p in _GREETING_PATTERNS)


def phrase(kind: str, limit: int = 8) -> list[str]:
    """Mined phrases of a kind, filtered for the character's register.

    kind ∈ {"greetings", "farewells", "backchannels", "dont_know"}
    Returns items ordered by corpus frequency.
    """
    _load()
    if not _phrases:
        return []
    out = []
    for item in _phrases.get(kind, []):
        t = item["text"]
        if not _CLEAN.match(t):
            continue          # reject digits, punctuation debris, usernames
        words = t.split()
        if len(words) > 4:
            continue
        if t in _REGISTER_OK_WORDS or all(w in _REGISTER_OK_WORDS for w in words):
            out.append(t)
        elif kind == "dont_know" and len(words) <= 4:
            # "not sure" family is register-neutral even if not in the set
            if any(w in ("know", "idea", "sure") for w in words):
                out.append(t)
        elif kind in ("greetings", "farewells") and t in (
                "hi", "hello", "hey", "bye", "goodbye", "good night",
                "good night all", "see you", "see ya", "later"):
            out.append(t)
        if len(out) >= limit:
            break
    return out
