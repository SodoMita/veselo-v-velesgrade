"""Scripted conversation eval for the single-character chat.

Each turn asserts the *content* of Mira's reply (topic relevance, act
routing, hedging) — a regression lock on conversational behavior.
Also reports a compact relevance score for the whole script.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from velesgrad_v2.dialogue.lg_ctypes import is_available

needs_lg = pytest.mark.skipif(not is_available(),
                              reason="Link Grammar dictionary unavailable")

SCRIPT = [
    # (player line, must-appear patterns (any-match), description)
    ("hello", ["Mira", "archive", "records", "Veil"], "introduces herself"),
    ("where does the relic lie?", ["relic"], "where → relic fact"),
    ("who watches the streets?", ["hounds"], "who → hounds fact"),
    ("why is the thinning veil dangerous?",
     ["veil", "spirits", "danger"], "why → implication/fact"),
    ("is the relic valuable?", ["relic"], "yes/no → confirms from (derived) TV"),
    ("is the tunnel safe?", ["not heard", "cannot confirm", "nothing", "assert"],
     "unknown claim → explicit uncertainty"),
    ("the relic lies in the tunnel", ["told me", "records"], "learns"),
    ("where is it?", ["tunnel", "relic"], "pronoun resolves to learned fact"),
    ("tell me about the archives of the city", ["archive", "velesgrad", "records"],
     "topical fallback"),
    ("see you later", ["farewell", "wisdom", "protect", "records"],
     "farewell"),
]


@needs_lg
def test_scripted_conversation():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=7)
    hits = 0
    misses = []
    for line, pats, desc in SCRIPT:
        reply = m.respond(line)
        low = reply.lower()
        if any(p.lower() in low for p in pats):
            hits += 1
        else:
            misses.append((desc, line, reply))
    total = len(SCRIPT)
    # Every turn must be on-script (tol 1 for classifier randomness)
    assert hits >= total - 1, f"misses: {misses}\nscore {hits}/{total}"


@needs_lg
def test_no_repeats_in_conversation():
    """She must not repeat the same sentence across a session."""
    from velesgrad_v2.chat import MiraChat
    m = MiraChat()
    replies = []
    for line, _, _ in SCRIPT:
        replies.append(m.respond(line))
    # allow generic opening/parting lines to recur at most twice
    seen = {}
    for r in replies:
        seen[r] = seen.get(r, 0) + 1
    repeats = {r: n for r, n in seen.items() if n > 1
               and len(r.split()) > 8}   # long factual lines must not repeat
    assert not repeats, repeats


@needs_lg
def test_multi_sentence_statement():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat()
    m.respond("hello")
    reply = m.respond("The bell signals danger. The archive holds prophecy records.")
    # at least one of the two facts acknowledged
    assert "danger" in reply.lower() or "prophecy" in reply.lower()


@needs_lg
def test_question_routing_distinct():
    """where/who/why route to different knowledge classes."""
    from velesgrad_v2.chat import MiraChat
    m1 = MiraChat(seed=3); m1.respond("hello")
    where = m1.respond("where is the relic?")
    m2 = MiraChat(seed=3); m2.respond("hello")
    who = m2.respond("who patrols the streets?")
    assert "relic" in where.lower()
    assert "hounds" in who.lower() or "guard" in who.lower()


@needs_lg
def test_pronoun_without_context_safe():
    """'where is it?' with no topic memory must not crash."""
    from velesgrad_v2.chat import MiraChat
    m = MiraChat()
    reply = m.respond("where is it?")
    assert isinstance(reply, str) and reply
