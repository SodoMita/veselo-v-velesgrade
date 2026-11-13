"""
mayfly_judgment.py – Should Mira answer this message at all, and how?

A chat room is not a chatbot's inbox. Answering every line that mentions her
makes her a nuisance, and answering a "thanks, bye" invites an endless tail.
This module makes that choice explicit and returns the reason, so the log
shows her reasoning.

Inputs: the message text, who sent it, what Mira has said to that sender
recently, and when. No network, no randomness, so it is fully testable.

Kinds (from the text):
  question   – asks something ("what", "who", "is ...?", "tell me ...")
  statement  – says something of substance, addressed to her
  greeting   – "hello mira", "good evening"
  closing    – thanks, goodbye, acknowledgements ("ok", "lol", "see you")
  empty      – nothing after her name

Decision rules, first match wins:
  1. empty                                  → silent
  2. closing                                → silent (no reply to a thank-you)
  3. sender is flooding (≥4 addressed msgs in 2 min, and not a question)
                                            → silent, let others speak
  4. she spoke to this sender <20 s ago, and the message is a short
     statement without a question            → silent, let the exchange breathe
  5. greeting she already greeted this sender with in the last 10 min
                                            → silent
  6. question                               → answer
  7. greeting                               → answer briefly
  8. statement with ≥4 words on a topic she knows → answer (she reflects)
     statement she has nothing to add to          → silent
  9. otherwise                              → silent
"""

import re
from dataclasses import dataclass, field

FLOOD_WINDOW = 120.0
FLOOD_LIMIT = 4
REPLY_COOLDOWN = 20.0
GREETING_MEMORY = 600.0

_WH = {"what", "who", "whom", "whose", "why", "how", "when", "where", "which",
       "is", "are", "was", "were", "do", "does", "did", "can", "could", "would",
       "should", "will", "have", "has", "tell", "explain", "describe", "name"}
_CLOSING = re.compile(
    r"^(thanks|thank you|thx|ty|ok|okay|cool|nice|great|lol|haha|hmm|bye|goodbye|"
    r"good night|goodnight|see you|farewell|got it|understood)\b", re.I)
_GREETING = re.compile(
    r"^(hello|hi|hey|greetings|good (morning|evening|afternoon|day)|well met|welcome|"
    r"salute)\b", re.I)


@dataclass
class Decision:
    reply: bool
    kind: str
    reason: str


@dataclass
class SenderState:
    """What Mira remembers about one sender. Filled by the bridge."""
    addressed_times: list = field(default_factory=list)   # when they addressed her
    last_reply_at: float = -1e9
    last_greeted_at: float = -1e9


_QUESTION_OPENERS = {"what", "who", "why", "how", "when", "where", "which",
                     "do", "does", "did", "can", "could", "would", "is", "are"}


def classify(text: str) -> str:
    t = text.strip()
    if not t:
        return "empty"
    words = re.findall(r"[a-z']+", t.lower())
    # "thanks", "thanks, Mira, that was helpful", "ok then, bye" are closings,
    # unless a question follows the acknowledgement ("ok, what is the veil?")
    if (_CLOSING.match(t) and "?" not in t and len(words) <= 12
            and not any(w in _QUESTION_OPENERS for w in words[1:3])):
        return "closing"
    if _GREETING.match(t) and len(t.split()) <= 6 and "?" not in t:
        return "greeting"
    if t.endswith("?") or (words and words[0] in _WH):
        return "question"
    return "statement"


def decide(text: str, state: SenderState, now: float, relevant: bool = True) -> Decision:
    """relevant: does Mira have anything to say about the words in this message?
    Questions are always answered; statements only when she has something on the topic."""
    kind = classify(text)
    recent = [t for t in state.addressed_times if now - t < FLOOD_WINDOW]

    if kind == "empty":
        return Decision(False, kind, "nothing was said after her name")
    if kind == "closing":
        return Decision(False, kind, "a thank-you or farewell needs no answer; silence closes it")
    if len(recent) >= FLOOD_LIMIT and kind != "question":
        return Decision(False, kind,
                        f"{len(recent)} messages to her in two minutes; giving others the floor")
    if (now - state.last_reply_at < REPLY_COOLDOWN and kind == "statement"
            and len(text.split()) < 6 and "?" not in text):
        return Decision(False, kind, "she has just answered; a short remark does not need a reply")
    if kind == "greeting" and now - state.last_greeted_at < GREETING_MEMORY:
        return Decision(False, kind, "already greeted this person recently")
    if kind == "question":
        return Decision(True, kind, "a question deserves an answer")
    if kind == "greeting":
        return Decision(True, kind, "a greeting, answered briefly")
    if kind == "statement" and len(text.split()) >= 4 and relevant:
        return Decision(True, kind, "a statement on something she knows; she reflects on it")
    if kind == "statement" and len(text.split()) >= 4:
        return Decision(False, kind, "a statement she has nothing to add to")
    return Decision(False, kind, "too little to respond to")
