#!/usr/bin/env python3
"""chat_eval.py – Scripted conversation eval, human-readable.

Runs the same 10-turn script as tests/test_chat_quality.py and prints each
Q/A pair with a PASS/FAIL on expected content. Exit code 0 always; it is a
report, the test suite is the gate.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from velesgrad_v2.dialogue.lg_ctypes import is_available


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


def main():
    from velesgrad_v2.chat import MiraChat
    if not is_available():
        print("Link Grammar dictionary missing — run data/fetch_lg_dict.sh")
        return
    m = MiraChat(seed=7)
    hits = 0
    print("=== Mira conversation eval (10 turns) ===")
    for line, pats, desc in SCRIPT:
        reply = m.respond(line)
        low = reply.lower()
        ok = any(p.lower() in low for p in pats)
        hits += ok
        print(f"\n  you:  {line}")
        print(f"  Mira: {reply}")
        print(f"        [{'PASS' if ok else 'FAIL'}] {desc}")
    print(f"\nscore: {hits}/{len(SCRIPT)} turns on-script")


if __name__ == "__main__":
    main()
